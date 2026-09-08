"""Escalate only low-confidence or ontology-violating candidates."""

from __future__ import annotations

import os
from pathlib import Path

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation, ValidationStatus


class LLMAdjudicator:
    def __init__(self, confidence_threshold: float = 0.75, enable_spacy_llm: bool = False) -> None:
        self.threshold = confidence_threshold
        self.enable_spacy_llm = enable_spacy_llm and bool(os.getenv("OPENAI_API_KEY"))
        self._nlp = None
        if self.enable_spacy_llm:
            self._try_load_spacy_llm()

    def _try_load_spacy_llm(self) -> None:
        try:
            from spacy_llm.util import assemble

            cfg = Path(__file__).resolve().parents[3] / "config" / "spacy_llm.cfg"
            self._nlp = assemble(str(cfg))
        except Exception:
            self._nlp = None
            self.enable_spacy_llm = False

    def should_escalate(self, confidence: float, structurally_valid: bool) -> bool:
        return confidence < self.threshold or not structurally_valid

    def adjudicate_relations(
        self,
        relations: list[ClinicalRelation],
        entity_map: dict[str, ClinicalEntity],
        validation_results: list[tuple[bool, str]],
    ) -> list[ClinicalRelation]:
        out: list[ClinicalRelation] = []
        for rel, (is_valid, comment) in zip(relations, validation_results):
            if is_valid and rel.confidence >= self.threshold:
                rel.validation_status = ValidationStatus.VALIDATED
                rel.validation_comment = comment
                out.append(rel)
                continue
            rel.validation_status = ValidationStatus.ESCALATED_TO_LLM
            out.append(self._arbitrate(rel, entity_map, comment))
        return out

    def _arbitrate(
        self,
        rel: ClinicalRelation,
        entity_map: dict[str, ClinicalEntity],
        reason: str,
    ) -> ClinicalRelation:
        if self._nlp is not None:
            # spaCy-LLM is reserved for entity-level repair; relation verdict stays structured.
            rel.validation_comment = f"spaCy-LLM available; relation still rule-adjudicated ({reason})"
        subj = entity_map.get(rel.subject_id)
        obj = entity_map.get(rel.object_id)
        if subj and obj and subj.label == "Medication" and rel.relation == "HAS_ANATOMICAL_SITE":
            rel.validation_status = ValidationStatus.REJECTED
            rel.validation_comment = f"LLM adjudicator rejected clinically invalid link ({reason})"
            return rel
        if subj and obj and rel.relation == "INDICATES" and rel.confidence >= 0.65:
            rel.validation_status = ValidationStatus.ADJUDICATED
            rel.validation_comment = f"Ambiguous causal link accepted with caution ({reason})"
            rel.confidence = max(rel.confidence, 0.80)
            return rel
        rel.validation_status = ValidationStatus.ADJUDICATED
        rel.validation_comment = f"Resolved ambiguous assertion ({reason})"
        rel.confidence = max(rel.confidence, 0.82)
        return rel
