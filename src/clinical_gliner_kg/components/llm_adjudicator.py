"""Escalate only low-confidence or ontology-violating candidates."""

from __future__ import annotations

import os
from pathlib import Path

from clinical_gliner_kg.components.llm_client import GOOGLE_OPENAI_BASE, chat_complete, resolve_api_key
from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation, DecisionEvent, ValidationStatus


class LLMAdjudicator:
    def __init__(
        self,
        confidence_threshold: float = 0.75,
        enable_spacy_llm: bool = False,
        provider: str = "none",
        openai_model: str = "gpt-4o-mini",
        openai_base_url: str = "https://api.openai.com/v1",
        openai_token_env: str = "OPENAI_API_KEY",
        google_model: str = "gemini-2.0-flash",
        google_base_url: str = GOOGLE_OPENAI_BASE,
        google_token_env: str = "GOOGLE_API_KEY",
        openai_compat_model: str = "gpt-4o-mini",
        openai_compat_base_url: str = "https://api.openai.com/v1",
        openai_compat_token_env: str = "OPENAI_API_KEY",
        vertex_model: str = "gemini-2.0-flash",
        vertex_location: str = "us-central1",
        gcp_project: str = "",
        azure_endpoint: str = "",
        azure_deployment: str = "",
        anthropic_model: str = "claude-3-5-sonnet-latest",
        temperature: float = 0.0,
    ) -> None:
        self.threshold = confidence_threshold
        self.provider = (provider or "none").lower()
        self.temperature = temperature
        self.openai_model = openai_model
        self.vertex_model = vertex_model
        self.vertex_location = vertex_location
        self.gcp_project = gcp_project or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_deployment = azure_deployment
        self.anthropic_model = anthropic_model
        self._nlp = None
        self._vertex = None
        self._chat = None  # dict with base_url, api_key, model
        want_llm = enable_spacy_llm or self.provider not in {"", "none"}
        self.enable_spacy_llm = False
        if not want_llm:
            return
        if self.provider in {"openai", "azure_openai", "anthropic"}:
            if self.provider == "openai" and os.getenv(openai_token_env):
                self._chat = {
                    "base_url": openai_base_url,
                    "api_key": os.getenv(openai_token_env, ""),
                    "model": openai_model,
                }
                self.enable_spacy_llm = True
                self._try_load_spacy_llm()
            elif self.provider == "azure_openai" and os.getenv("AZURE_OPENAI_API_KEY"):
                self.enable_spacy_llm = True
                self._try_load_spacy_llm()
            elif self.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
                self.enable_spacy_llm = True
                self._try_load_spacy_llm()
        elif self.provider in {"google", "gemini"}:
            key = resolve_api_key(google_token_env, "GOOGLE_API_KEY", "GEMINI_API_KEY")
            if key:
                self._chat = {
                    "base_url": google_base_url or GOOGLE_OPENAI_BASE,
                    "api_key": key,
                    "model": google_model,
                }
        elif self.provider in {"openai_compat", "openai-compatible", "compatible"}:
            key = resolve_api_key(openai_compat_token_env, "OPENAI_API_KEY")
            if key:
                self._chat = {
                    "base_url": openai_compat_base_url,
                    "api_key": key,
                    "model": openai_compat_model,
                }
        elif self.provider == "vertex":
            self._try_load_vertex()
        elif os.getenv("OPENAI_API_KEY"):
            self.provider = "openai"
            self._chat = {
                "base_url": openai_base_url,
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": openai_model,
            }
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

    @property
    def llm_ready(self) -> bool:
        return self._chat is not None or self._vertex is not None or self._nlp is not None

    def adjudicate_relations(
        self,
        relations: list[ClinicalRelation],
        entity_map: dict[str, ClinicalEntity],
        validation_results: list[tuple[bool, str]],
    ) -> list[ClinicalRelation]:
        out: list[ClinicalRelation] = []
        for rel, (is_valid, comment) in zip(relations, validation_results):
            original_conf = rel.confidence
            forbidden = (not is_valid) and comment.startswith("Ontology violation")
            if forbidden:
                rel.validation_status = ValidationStatus.REJECTED
                rel.validation_comment = comment
                rel.schema_verdict = "forbidden"
                rel.confidence = original_conf
                rel.history.append(DecisionEvent(actor="schema", decision="REJECTED", comment=comment))
                out.append(rel)
                continue
            if is_valid and rel.confidence >= self.threshold:
                rel.validation_status = ValidationStatus.VALIDATED
                rel.validation_comment = comment
                rel.schema_verdict = "allowed"
                rel.history.append(DecisionEvent(actor="schema", decision="VALIDATED", comment=comment))
                out.append(rel)
                continue
            rel.schema_verdict = "ambiguous" if is_valid else "unregistered"
            rel.validation_status = ValidationStatus.ESCALATED_TO_LLM
            rel.history.append(DecisionEvent(actor="schema", decision="ESCALATED_TO_LLM", comment=comment))
            out.append(self._arbitrate(rel, entity_map, comment, original_conf))
        return out

    def _backend_note(self) -> str:
        if self._chat is not None:
            return f"{self.provider}:{self._chat['model']}; "
        if self._nlp is not None:
            return f"{self.provider}/spaCy-LLM; "
        if self._vertex is not None:
            return f"vertex:{self.vertex_model} via ADC; "
        return ""

    def _arbitrate(
        self,
        rel: ClinicalRelation,
        entity_map: dict[str, ClinicalEntity],
        reason: str,
        original_conf: float,
    ) -> ClinicalRelation:
        rel.confidence = original_conf
        llm_ready = self._chat is not None or self._vertex is not None or self._nlp is not None
        if not llm_ready:
            rel.validation_status = ValidationStatus.NEEDS_REVIEW
            rel.validation_comment = f"No LLM configured; queued for review ({reason})"
            rel.history.append(DecisionEvent(actor="router", decision="NEEDS_REVIEW", comment=rel.validation_comment))
            return rel
        verdict = self._llm_verdict(rel, entity_map, reason)
        rel.adjudication_model = (self._chat or {}).get("model") if self._chat else (
            self.vertex_model if self._vertex is not None else self.provider
        )
        note = self._backend_note()
        if verdict == "REJECT":
            rel.validation_status = ValidationStatus.LLM_REJECTED
            rel.validation_comment = f"{note}LLM rejected ({reason})"
            rel.history.append(DecisionEvent(actor="llm", decision="LLM_REJECTED", comment=rel.validation_comment, model=rel.adjudication_model))
            return rel
        if verdict == "ACCEPT":
            rel.validation_status = ValidationStatus.LLM_VALIDATED
            rel.validation_comment = f"{note}LLM accepted ({reason})"
            rel.history.append(DecisionEvent(actor="llm", decision="LLM_VALIDATED", comment=rel.validation_comment, model=rel.adjudication_model))
            return rel
        if verdict == "CAUTION":
            rel.validation_status = ValidationStatus.NEEDS_REVIEW
            rel.validation_comment = f"{note}LLM returned CAUTION ({reason})"
            rel.history.append(DecisionEvent(actor="llm", decision="NEEDS_REVIEW", comment=rel.validation_comment, model=rel.adjudication_model))
            return rel
        rel.validation_status = ValidationStatus.NEEDS_REVIEW
        rel.validation_comment = f"{note}LLM unavailable or inconclusive ({reason})"
        rel.history.append(DecisionEvent(actor="llm", decision="NEEDS_REVIEW", comment=rel.validation_comment, model=rel.adjudication_model))
        return rel

    def _llm_verdict(
        self,
        rel: ClinicalRelation,
        entity_map: dict[str, ClinicalEntity],
        reason: str,
    ) -> str | None:
        if self._chat is None:
            return None
        subj = entity_map.get(rel.subject_id)
        obj = entity_map.get(rel.object_id)
        prompt = (
            "You adjudicate one clinical knowledge-graph triple. "
            "Reply with a single token: ACCEPT, REJECT, or CAUTION.\n"
            f"Subject: {(subj.text if subj else rel.subject_id)} ({subj.label if subj else '?'})\n"
            f"Relation: {rel.relation}\n"
            f"Object: {(obj.text if obj else rel.object_id)} ({obj.label if obj else '?'})\n"
            f"Reason the router escalated: {reason}\n"
        )
        try:
            content = chat_complete(
                base_url=self._chat["base_url"],
                api_key=self._chat["api_key"],
                model=self._chat["model"],
                messages=[
                    {"role": "system", "content": "You are a careful clinical KG adjudicator."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
        except Exception:
            return None
        token = content.split()[0].upper().strip(".,:; ") if content else ""
        if token in {"ACCEPT", "REJECT", "CAUTION"}:
            return token
        return None
