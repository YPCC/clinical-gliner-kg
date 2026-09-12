"""HIPAA PHI / PII detection, redaction, and policy enforcement gate."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from clinical_gliner_kg.models import ClinicalEntity

PHI_LABELS = {
    "PATIENT_NAME",
    "PROVIDER_NAME",
    "DATE_OF_BIRTH",
    "PHONE_NUMBER",
    "SSN",
    "MRN",
    "ADDRESS",
    "EMAIL",
    "ACCOUNT",
    "INTERNAL_ID",
    "CONTRACT_ID",
    "LOCATION",
}

GLINER_PII_LABELS = [
    "person",
    "email",
    "phone_number",
    "address",
    "date_of_birth",
    "ssn",
    "medical_record_number",
    "account_number",
    "organization",
    "city",
]


@dataclass
class PHIFinding:
    text: str
    label: str
    start: int
    end: int
    confidence: float
    source: str


class PHIPolicyGate:
    """Cascade: deterministic detectors → optional GLiNER PII model → policy action."""

    PATTERNS: list[tuple[str, str]] = [
        ("EMAIL", r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"),
        ("PHONE_NUMBER", r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}"),
        ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
        ("MRN", r"\b(?:MRN|Medical Record(?: Number)?)\s*[:#]?\s*[A-Z0-9-]{4,}\b"),
        ("DATE_OF_BIRTH", r"\b(?:DOB|Date of Birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
        ("ACCOUNT", r"\b(?:Acct|Account)\s*[:#]?\s*\d{4,}\b"),
        ("INTERNAL_ID", r"\bINC-\d+\b"),
        ("CONTRACT_ID", r"\bCNT-[A-Z0-9-]+\b"),
    ]

    def __init__(
        self,
        action: str = "tag",
        enable_gliner_pii: bool = False,
        pii_model: str | None = None,
    ) -> None:
        if action not in {"tag", "mask", "route"}:
            raise ValueError("action must be tag | mask | route")
        self.action = action
        self.enable_gliner_pii = enable_gliner_pii
        self.pii_model = pii_model or os.getenv("GLINER_PII_MODEL", "fastino/gliner2-privacy-filter-PII-multi")
        self._pii_model = None
        if enable_gliner_pii:
            self._try_load_pii_model()

    def _try_load_pii_model(self) -> None:
        try:
            from gliner2 import AutoExtractor

            name = self.pii_model
            self._pii_model = AutoExtractor.from_pretrained(name)
        except Exception:
            self._pii_model = None

    def detect(self, text: str) -> list[PHIFinding]:
        findings: list[PHIFinding] = []
        for label, pattern in self.PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                findings.append(
                    PHIFinding(
                        text=match.group(0),
                        label=label,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.99,
                        source="regex",
                    )
                )
        if self._pii_model is not None:
            try:
                raw = self._pii_model.extract_entities(text, GLINER_PII_LABELS, include_spans=True)
                grouped = raw.get("entities", {}) if isinstance(raw, dict) else {}
                for label, items in grouped.items():
                    for item in items if isinstance(items, list) else [items]:
                        if isinstance(item, dict):
                            findings.append(
                                PHIFinding(
                                    text=str(item.get("text", "")),
                                    label=str(label).upper(),
                                    start=int(item.get("start", 0)),
                                    end=int(item.get("end", 0)),
                                    confidence=float(item.get("confidence", 0.85)),
                                    source="gliner-pii",
                                )
                            )
            except Exception:
                pass
        return _dedupe_findings(findings)

    def apply(self, text: str, entities: list[ClinicalEntity]) -> tuple[str, list[ClinicalEntity], list[PHIFinding]]:
        findings = self.detect(text)
        sanitized = list(entities)
        out_text = _mask_by_offsets(text, findings) if self.action == "mask" else text
        for finding in findings:
            sanitized.append(
                ClinicalEntity(
                    id=f"phi_{finding.start}_{finding.end}",
                    text="[REDACTED_" + finding.label + "]" if self.action == "mask" else finding.text,
                    label=finding.label,
                    start_char=finding.start,
                    end_char=finding.end,
                    confidence=finding.confidence,
                    is_phi=True,
                    source_model=finding.source,
                )
            )
        for ent in sanitized:
            if ent.label in PHI_LABELS:
                ent.is_phi = True
                if self.action == "mask":
                    ent.text = f"[REDACTED_{ent.label}]"
        return out_text, sanitized, findings


def _dedupe_findings(findings: list[PHIFinding]) -> list[PHIFinding]:
    """Keep the longest / highest-confidence span when detectors overlap."""
    ordered = sorted(findings, key=lambda item: (item.start, -(item.end - item.start), -item.confidence))
    kept: list[PHIFinding] = []
    for item in ordered:
        if any(not (item.end <= other.start or item.start >= other.end) for other in kept):
            continue
        kept.append(item)
    return kept


def _mask_by_offsets(text: str, findings: list[PHIFinding]) -> str:
    """Replace using character offsets, right-to-left, so identical substrings elsewhere stay."""
    out = text
    for item in sorted(findings, key=lambda finding: finding.start, reverse=True):
        if item.start < 0 or item.end > len(out) or item.start >= item.end:
            continue
        token = f"[REDACTED_{item.label}]"
        out = out[: item.start] + token + out[item.end :]
    return out
