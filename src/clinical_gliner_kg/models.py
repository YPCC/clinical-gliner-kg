"""Data schemas for clinical entities, relations, provenance, and graph triples."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationStatus(str, Enum):
    """Do not collapse extraction, linking, schema, and LLM into one bit.

    Entity path: CANDIDATE → LINKED | UNLINKED
    Relation path: CANDIDATE → VALIDATED | REJECTED | NEEDS_REVIEW | LLM_*
    """

    CANDIDATE = "CANDIDATE"
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ESCALATED_TO_LLM = "ESCALATED_TO_LLM"
    LLM_VALIDATED = "LLM_VALIDATED"
    LLM_REJECTED = "LLM_REJECTED"
    ADJUDICATED = "ADJUDICATED"  # legacy; new code writes LLM_* or NEEDS_REVIEW


class DecisionEvent(BaseModel):
    """One step in an assertion's decision history."""

    at: str = Field(default_factory=_now)
    actor: str  # extractor | catalog | oak | schema | llm | store
    decision: str
    comment: str = ""
    model: str | None = None


class TerminologyLink(BaseModel):
    system: str
    code: str
    display: str
    match_score: float = 0.0
    method: str = "catalog"
    version: str = "catalog-ypcc-0.1"


class ClinicalEntity(BaseModel):
    id: str
    text: str
    label: str
    start_char: int
    end_char: int
    confidence: float
    is_phi: bool = False
    source_model: str = "heuristic"
    terminology: TerminologyLink | None = None
    validation_status: ValidationStatus = ValidationStatus.CANDIDATE
    linking_confidence: float = 0.0
    history: list[DecisionEvent] = Field(default_factory=list)
    idempotency_key: str = ""


class ClinicalRelation(BaseModel):
    subject_id: str
    relation: str
    object_id: str
    confidence: float
    source_model: str = "heuristic"
    validation_status: ValidationStatus = ValidationStatus.CANDIDATE
    validation_comment: str | None = None
    subject_start: int | None = None
    subject_end: int | None = None
    object_start: int | None = None
    object_end: int | None = None
    adjudication_model: str | None = None
    schema_verdict: str = ""
    history: list[DecisionEvent] = Field(default_factory=list)
    idempotency_key: str = ""


class ProvenanceMetadata(BaseModel):
    document_id: str
    extracted_at: str = Field(default_factory=_now)
    pipeline_version: str = "0.1.0"
    extraction_backend: str = "heuristic"
    escalation_used: bool = False
    llm_invoked: bool = False
    graph_target: str = "both"
    event_id: str | None = None


class EventEnvelope(BaseModel):
    """Unit of work for event-driven ingestion (JSONL today; Kafka later)."""

    document_id: str
    payload: str
    source: str = "file"
    observed_at: str = Field(default_factory=_now)
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    idempotency_key: str = ""

    def key(self) -> str:
        if self.idempotency_key:
            return self.idempotency_key
        digest = hashlib.sha256(f"{self.document_id}|{self.payload}".encode("utf-8")).hexdigest()[:24]
        return f"evt_{digest}"


class ClinicalKnowledgeGraph(BaseModel):
    document_id: str
    text: str = ""
    entities: list[ClinicalEntity]
    relations: list[ClinicalRelation]
    provenance: ProvenanceMetadata
    cypher_queries: list[str] = Field(default_factory=list)
    json_ld: dict[str, Any] = Field(default_factory=dict)
    rdf_jsonld: dict[str, Any] = Field(default_factory=dict)
    turtle: str = ""
    rdfxml: str = ""
    sparql: dict[str, list[dict[str, str]]] = Field(default_factory=dict)


def assertion_key(document_id: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in (document_id, *parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def stamp_entity_keys(document_id: str, entity: ClinicalEntity) -> ClinicalEntity:
    entity.idempotency_key = assertion_key(
        document_id, "ent", entity.start_char, entity.end_char, entity.label, entity.text.lower()
    )
    return entity


def stamp_relation_keys(document_id: str, rel: ClinicalRelation) -> ClinicalRelation:
    rel.idempotency_key = assertion_key(
        document_id,
        "rel",
        rel.relation,
        rel.subject_id,
        rel.object_id,
        rel.subject_start,
        rel.object_start,
    )
    return rel
