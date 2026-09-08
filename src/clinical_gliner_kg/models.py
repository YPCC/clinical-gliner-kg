"""Data schemas for clinical entities, relations, provenance, and graph triples."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    ESCALATED_TO_LLM = "ESCALATED_TO_LLM"
    ADJUDICATED = "ADJUDICATED"
    REJECTED = "REJECTED"
    CANDIDATE = "CANDIDATE"


class TerminologyLink(BaseModel):
    system: str
    code: str
    display: str
    match_score: float = 0.0


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


class ClinicalRelation(BaseModel):
    subject_id: str
    relation: str
    object_id: str
    confidence: float
    source_model: str = "heuristic"
    validation_status: ValidationStatus = ValidationStatus.CANDIDATE
    validation_comment: str | None = None


class ProvenanceMetadata(BaseModel):
    document_id: str
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pipeline_version: str = "0.1.0"
    extraction_backend: str = "heuristic"
    escalation_used: bool = False


class ClinicalKnowledgeGraph(BaseModel):
    document_id: str
    text: str = ""
    entities: list[ClinicalEntity]
    relations: list[ClinicalRelation]
    provenance: ProvenanceMetadata
    cypher_queries: list[str] = Field(default_factory=list)
    json_ld: dict[str, Any] = Field(default_factory=dict)
    turtle: str = ""
