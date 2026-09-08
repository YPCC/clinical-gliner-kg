"""Orchestrate GLiNER → PHI gate → ontology → LLM router → provenance KG."""

from __future__ import annotations

import uuid
from pathlib import Path

from clinical_gliner_kg.backends import resolve_backend
from clinical_gliner_kg.components.llm_adjudicator import LLMAdjudicator
from clinical_gliner_kg.components.ontology_linker import OntologyValidationEngine
from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.graph.emitter import GraphEmitter
from clinical_gliner_kg.models import (
    ClinicalKnowledgeGraph,
    ProvenanceMetadata,
)
from clinical_gliner_kg.settings import PipelineSettings, load_settings


def load_config(path: Path | None = None) -> dict:
    """Backward-compatible wrapper; prefer `load_settings`."""
    return load_settings(path).model_dump()


class ClinicalSemanticExtractionPipeline:
    def __init__(
        self,
        backend: str | None = None,
        confidence_threshold: float | None = None,
        phi_action: str | None = None,
        enable_gliner_pii: bool | None = None,
        enable_spacy_llm: bool | None = None,
        config_path: Path | str | None = None,
        labels: list[str] | None = None,
        relations: list[str] | None = None,
        enable_relations: bool | None = None,
        settings: PipelineSettings | None = None,
    ) -> None:
        cfg = settings or load_settings(config_path)
        self.settings = cfg
        backend_name = backend or cfg.backend
        threshold = cfg.confidence_threshold if confidence_threshold is None else confidence_threshold
        gliner = cfg.gliner
        backend_kwargs = {
            "model_name": gliner.model,
            "threshold": gliner.threshold,
            "enable_relations": gliner.enable_relations if enable_relations is None else enable_relations,
            "enable_joint": gliner.enable_joint,
            "mode": gliner.mode,
            "hf_endpoint": gliner.huggingface.endpoint,
            "hf_token_env": gliner.huggingface.token_env,
            "pioneer_base_url": gliner.pioneer.base_url,
            "pioneer_token_env": gliner.pioneer.token_env,
            "labels": labels or [item.lower() for item in cfg.clinical_labels],
            "relations": relations or list(cfg.relation_types),
        }
        if backend_name == "gliner_spacy":
            backend_kwargs = {"model_name": gliner.spacy.model, "threshold": gliner.threshold}
        self.extractor = resolve_backend(backend_name, **backend_kwargs)
        phi_on = cfg.phi.enable_gliner_pii if enable_gliner_pii is None else enable_gliner_pii
        self.phi_gate = PHIPolicyGate(
            action=phi_action or cfg.phi.action,
            enable_gliner_pii=phi_on,
            pii_model=gliner.pii_model,
        )
        self.ontology = OntologyValidationEngine(
            oak_selectors=cfg.oak_selectors(),
            oak_mode=cfg.oaklib.mode,
            oak_eager=cfg.oaklib.eager,
            bioportal_token_env=cfg.oaklib.bioportal.token_env,
        )
        llm_enable = cfg.llm.enable if enable_spacy_llm is None else enable_spacy_llm
        self.adjudicator = LLMAdjudicator(
            confidence_threshold=threshold,
            enable_spacy_llm=llm_enable,
            provider=cfg.llm.provider if llm_enable or cfg.llm.provider != "none" else "none",
            openai_model=cfg.llm.openai.model,
            openai_base_url=cfg.llm.openai.base_url,
            openai_token_env=cfg.llm.openai.token_env,
            google_model=cfg.llm.google.model,
            google_base_url=cfg.llm.google.base_url,
            google_token_env=cfg.llm.google.token_env,
            openai_compat_model=cfg.llm.openai_compat.model,
            openai_compat_base_url=cfg.llm.openai_compat.base_url,
            openai_compat_token_env=cfg.llm.openai_compat.token_env,
            vertex_model=cfg.llm.vertex.model,
            vertex_location=cfg.gcp.location or cfg.llm.vertex.location,
            gcp_project=cfg.gcp.project,
            azure_endpoint=cfg.llm.azure_openai.endpoint,
            azure_deployment=cfg.llm.azure_openai.deployment,
            anthropic_model=cfg.llm.anthropic.model,
            temperature=cfg.llm.openai.temperature,
        )
        self.emitter = GraphEmitter()
        self.pipeline_version = cfg.pipeline_version

    def process_document(self, text: str, document_id: str | None = None) -> ClinicalKnowledgeGraph:
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:8]}"
        entities, relations = self.extractor.extract(text)
        text_out, entities, _findings = self.phi_gate.apply(text, entities)
        entities = [self.ontology.link_entity(ent) for ent in entities]
        entity_map = {ent.id: ent for ent in entities}
        validation = [self.ontology.validate_relation(rel, entity_map) for rel in relations]
        llm_ready = self.adjudicator.llm_ready
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
                llm_invoked=escalation and llm_ready,
            ),
        )
        kg.cypher_queries = self.emitter.emit_cypher(kg)
        kg.json_ld = self.emitter.emit_json_ld(kg)
        kg.turtle = self.emitter.emit_turtle(kg)
        return kg
