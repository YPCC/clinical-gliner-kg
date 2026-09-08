"""Data schemas for clinical entities, relations, provenance, and graph triples."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class TerminologyLink(BaseModel):
    system: str
    code: str
    display: str
    match_score: float = 0.0
    method: str = "catalog"


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


class ProvenanceMetadata(BaseModel):
    document_id: str
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pipeline_version: str = "0.1.0"
    extraction_backend: str = "heuristic"
    escalation_used: bool = False
    llm_invoked: bool = False


class ClinicalKnowledgeGraph(BaseModel):
    document_id: str
    text: str = ""
    entities: list[ClinicalEntity]
    relations: list[ClinicalRelation]
    provenance: ProvenanceMetadata
    cypher_queries: list[str] = Field(default_factory=list)
    json_ld: dict[str, Any] = Field(default_factory=dict)
    turtle: str = ""
