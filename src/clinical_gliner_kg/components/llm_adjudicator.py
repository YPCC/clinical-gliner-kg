"""Escalate only low-confidence or ontology-violating candidates."""

from __future__ import annotations

import os
from pathlib import Path

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation, ValidationStatus


class LLMAdjudicator:
    def __init__(
        self,
        confidence_threshold: float = 0.75,
        enable_spacy_llm: bool = False,
        provider: str = "none",
        openai_model: str = "gpt-4o-mini",
        vertex_model: str = "gemini-2.0-flash",
        vertex_location: str = "us-central1",
        gcp_project: str = "",
        azure_endpoint: str = "",
        azure_deployment: str = "",
        anthropic_model: str = "claude-3-5-sonnet-latest",
    ) -> None:
        self.threshold = confidence_threshold
        self.provider = (provider or "none").lower()
        self.openai_model = openai_model
        self.vertex_model = vertex_model
        self.vertex_location = vertex_location
        self.gcp_project = gcp_project or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_deployment = azure_deployment
        self.anthropic_model = anthropic_model
        self._nlp = None
        self._vertex = None
        want_llm = enable_spacy_llm or self.provider not in {"", "none"}
        self.enable_spacy_llm = False
        if want_llm and self.provider in {"openai", "azure_openai"}:
            if self.provider == "openai" and os.getenv("OPENAI_API_KEY"):
                self.enable_spacy_llm = True
                self._try_load_spacy_llm()
            elif self.provider == "azure_openai" and os.getenv("AZURE_OPENAI_API_KEY"):
                self.enable_spacy_llm = True
                self._try_load_spacy_llm()
        elif want_llm and self.provider == "vertex":
            self._try_load_vertex()
        elif want_llm and self.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            self.enable_spacy_llm = True
            self._try_load_spacy_llm()
        elif want_llm and os.getenv("OPENAI_API_KEY"):
            self.provider = "openai"
            self.enable_spacy_llm = True
            self._try_load_spacy_llm()

    def _try_load_spacy_llm(self) -> None:
        try:
            from spacy_llm.util import assemble

            cfg = Path(__file__).resolve().parents[3] / "config" / "spacy_llm.cfg"
            os.environ.setdefault("OPENAI_MODEL", self.openai_model)
            self._nlp = assemble(str(cfg))
        except Exception:
            self._nlp = None
            self.enable_spacy_llm = False

    def _try_load_vertex(self) -> None:
        """Vertex Gemini via ADC (`google.auth.default()`)."""
        try:
            import google.auth
            import vertexai
            from vertexai.generative_models import GenerativeModel

            credentials, project = google.auth.default()
            project = self.gcp_project or project
            if not project:
                return
            vertexai.init(project=project, location=self.vertex_location, credentials=credentials)
            self._vertex = GenerativeModel(self.vertex_model)
        except Exception:
            self._vertex = None

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
        backend_note = ""
        if self._nlp is not None:
            backend_note = f"{self.provider}/spaCy-LLM available; "
        elif self._vertex is not None:
            backend_note = f"vertex:{self.vertex_model} via ADC available; "
        subj = entity_map.get(rel.subject_id)
        obj = entity_map.get(rel.object_id)
        if subj and obj and subj.label == "Medication" and rel.relation == "HAS_ANATOMICAL_SITE":
            rel.validation_status = ValidationStatus.REJECTED
            rel.validation_comment = f"{backend_note}rejected clinically invalid link ({reason})"
            return rel
        if subj and obj and rel.relation == "INDICATES" and rel.confidence >= 0.65:
            rel.validation_status = ValidationStatus.ADJUDICATED
            rel.validation_comment = f"{backend_note}ambiguous causal link accepted with caution ({reason})"
            rel.confidence = max(rel.confidence, 0.80)
            return rel
        rel.validation_status = ValidationStatus.ADJUDICATED
        rel.validation_comment = f"{backend_note}resolved ambiguous assertion ({reason})"
        rel.confidence = max(rel.confidence, 0.82)
        return rel
