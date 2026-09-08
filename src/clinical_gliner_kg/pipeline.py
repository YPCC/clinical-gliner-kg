"""Orchestrate GLiNER → PHI gate → ontology → LLM router → provenance KG."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import yaml

from clinical_gliner_kg.backends import resolve_backend
from clinical_gliner_kg.components.llm_adjudicator import LLMAdjudicator
from clinical_gliner_kg.components.ontology_linker import OntologyValidationEngine
from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.graph.emitter import GraphEmitter
from clinical_gliner_kg.models import (
    ClinicalKnowledgeGraph,
    ProvenanceMetadata,
    ValidationStatus,
)


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or Path(__file__).resolve().parents[2] / "config" / "pipeline.yaml"
    if cfg_path.exists():
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return {}


class ClinicalSemanticExtractionPipeline:
    def __init__(
        self,
        backend: str | None = None,
        confidence_threshold: float | None = None,
        phi_action: str = "tag",
        enable_gliner_pii: bool = False,
        enable_spacy_llm: bool = False,
        config_path: Path | None = None,
    ) -> None:
        cfg = load_config(config_path)
        backend_name = backend or os.getenv("CLINICAL_GLINER_BACKEND") or cfg.get("backend", "auto")
        threshold = confidence_threshold if confidence_threshold is not None else float(cfg.get("confidence_threshold", 0.75))
        self.extractor = resolve_backend(
            backend_name,
            model_name=os.getenv("GLINER25_MODEL", cfg.get("gliner25_model")),
        )
        self.phi_gate = PHIPolicyGate(action=phi_action or cfg.get("phi_action", "tag"), enable_gliner_pii=enable_gliner_pii)
        self.ontology = OntologyValidationEngine()
        self.adjudicator = LLMAdjudicator(confidence_threshold=threshold, enable_spacy_llm=enable_spacy_llm)
        self.emitter = GraphEmitter()
        self.pipeline_version = str(cfg.get("pipeline_version", "0.1.0-cascaded"))

    def process_document(self, text: str, document_id: str | None = None) -> ClinicalKnowledgeGraph:
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:8]}"
        entities, relations = self.extractor.extract(text)
        text_out, entities, _findings = self.phi_gate.apply(text, entities)
        entities = [self.ontology.link_entity(ent) for ent in entities]
        for ent in entities:
            if ent.validation_status == ValidationStatus.CANDIDATE:
                ent.validation_status = ValidationStatus.VALIDATED
        entity_map = {ent.id: ent for ent in entities}
        validation = [self.ontology.validate_relation(rel, entity_map) for rel in relations]
        escalation = any(
            self.adjudicator.should_escalate(rel.confidence, is_valid)
            for rel, (is_valid, _) in zip(relations, validation)
        )
        final_relations = self.adjudicator.adjudicate_relations(relations, entity_map, validation)
        kg = ClinicalKnowledgeGraph(
            document_id=doc_id,
            text=text_out,
            entities=entities,
            relations=final_relations,
            provenance=ProvenanceMetadata(
                document_id=doc_id,
                pipeline_version=self.pipeline_version,
                extraction_backend=getattr(self.extractor, "name", "unknown"),
                escalation_used=escalation,
            ),
        )
        kg.cypher_queries = self.emitter.emit_cypher(kg)
        kg.json_ld = self.emitter.emit_json_ld(kg)
        kg.turtle = self.emitter.emit_turtle(kg)
        return kg
