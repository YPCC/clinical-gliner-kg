"""CINEX reporting-guideline JSON (https://www.cinex-guideline.org/).

CINEX is a *study report* checklist (29 items, five dimensions), not a graph
serialisation. We auto-fill what this repository can honestly claim and mark
the rest partial / not_reported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from clinical_gliner_kg.models import ClinicalKnowledgeGraph
from clinical_gliner_kg.settings import REPO_ROOT, PipelineSettings

DEFAULT_ITEMS = REPO_ROOT / "config" / "cinex_items.yaml"

_STATUS_REPORTED = "reported"
_STATUS_PARTIAL = "partial"
_STATUS_NOT = "not_reported"


def _load_catalog(path: Path | None = None) -> dict[str, Any]:
    cfg = Path(path) if path else DEFAULT_ITEMS
    if not cfg.exists():
        return {"guideline": "CINEX", "url": "https://www.cinex-guideline.org/", "dimensions": {}}
    return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}


def build_cinex_report(
    kg: ClinicalKnowledgeGraph | None = None,
    settings: PipelineSettings | None = None,
    *,
    outcomes: dict[str, Any] | None = None,
    extra_items: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a CINEX digital-form-shaped JSON object."""
    catalog = _load_catalog()
    answers = _autofill(kg, settings, outcomes or {}, extra_items or {})
    items: list[dict[str, Any]] = []
    for dim_key, dim in (catalog.get("dimensions") or {}).items():
        for spec in dim.get("items") or []:
            item_id = spec["id"]
            filled = answers.get(item_id, {})
            items.append(
                {
                    "id": item_id,
                    "dimension": dim_key,
                    "title": spec.get("title", item_id),
                    "status": filled.get("status", _STATUS_NOT),
                    "response": filled.get("response", ""),
                }
            )
    reported = sum(1 for item in items if item["status"] == _STATUS_REPORTED)
    partial = sum(1 for item in items if item["status"] == _STATUS_PARTIAL)
    return {
        "guideline": catalog.get("guideline", "CINEX"),
        "url": catalog.get("url", "https://www.cinex-guideline.org/"),
        "citation": catalog.get("citation", ""),
        "completeness": {
            "n_items": len(items),
            "reported": reported,
            "partial": partial,
            "not_reported": len(items) - reported - partial,
        },
        "document_id": kg.document_id if kg else None,
        "outcomes": outcomes or {},
        "items": items,
    }


def _autofill(
    kg: ClinicalKnowledgeGraph | None,
    settings: PipelineSettings | None,
    outcomes: dict[str, Any],
    extra: dict[str, str],
) -> dict[str, dict[str, str]]:
    labels = list(settings.clinical_labels) if settings else []
    rels = list(settings.relation_types) if settings else []
    backend = kg.provenance.extraction_backend if kg else (settings.backend if settings else "unknown")
    graph_target = (
        kg.provenance.graph_target if kg else (settings.graph.target if settings else "both")
    )
    llm = settings.llm if settings else None
    oak = settings.oaklib if settings else None
    filled: dict[str, dict[str, str]] = {
        "IM1": {
            "status": _STATUS_REPORTED,
            "response": (
                "High-recall clinical extraction control plane: GLiNER sensing → PHI/PII/BII gate → "
                "terminology grounding → schema validation → selective LLM → provenance KG "
                "for RAG, analytics, and agents. Not a certified medical device."
            ),
        },
        "IM2": {
            "status": _STATUS_REPORTED,
            "response": ", ".join(labels) or "Patient, Condition, Medication, Laboratory_Test, …",
        },
        "IM3": {
            "status": _STATUS_REPORTED,
            "response": ", ".join(rels) or "HAS_CONDITION, TAKES, TREATS, HAS_VALUE, INDICATES, …",
        },
        "IM4": {
            "status": _STATUS_PARTIAL,
            "response": (
                "Catalog slice of SNOMED CT, RxNorm, LOINC (version catalog-ypcc-0.1) plus oaklib "
                f"mode={oak.mode if oak else 'local'} over local OBO/SQLite. Not an official RF2/RxNorm release."
            ),
        },
        "IM5": {
            "status": _STATUS_PARTIAL,
            "response": (
                "Spans are extracted as mentions; catalog/oaklib linking yields concepts; "
                "clin:Assertion wraps relations. Mention→Concept→Assertion is only partially factored."
            ),
        },
        "A1": {
            "status": _STATUS_REPORTED,
            "response": (
                "ClinicalSemanticExtractionPipeline.process_document: backend → PHI gate → "
                "oaklib/catalog → domain-range router → optional LLM → LPG and/or RDFS emitter."
            ),
        },
        "A2": {
            "status": _STATUS_REPORTED,
            "response": (
                f"backend={backend}; gliner.model={settings.gliner.model if settings else 'n/a'}; "
                f"gliner.mode={settings.gliner.mode if settings else 'n/a'}; "
                f"llm.provider={llm.provider if llm else 'none'}."
            ),
        },
        "A3": {
            "status": _STATUS_REPORTED,
            "response": (
                f"PHI action={settings.phi.action if settings else 'tag'}; "
                "offset mask + overlap dedupe; JSON ontology_rules.json; RelEx binds by character span."
            ),
        },
        "A4": {
            "status": _STATUS_REPORTED,
            "response": (
                "LLM only on low-confidence or unregistered pairs when configured. "
                "ACCEPT→LLM_VALIDATED, REJECT→LLM_REJECTED, CAUTION→NEEDS_REVIEW. "
                "No LLM → NEEDS_REVIEW. Human review queue is not implemented."
            ),
        },
        "A5": {
            "status": _STATUS_REPORTED,
            "response": (
                f"Default local weights + local oaklib. graph.target={graph_target}. "
                "Hosted Pioneer/HF/OLS/BioPortal/LLM are opt-in via pipeline.yaml."
            ),
        },
        "D1": {
            "status": _STATUS_PARTIAL,
            "response": (
                "Bundled synthetic notes for CI; optional NCBI Disease and BC5CDR literature spike. "
                "n2c2/MIMIC are catalogued but not shipped (DUA)."
            ),
        },
        "D2": {
            "status": _STATUS_REPORTED,
            "response": "English clinical / biomedical prose (synthetic notes; PubTator literature).",
        },
        "D3": {
            "status": _STATUS_NOT,
            "response": "No patient cohort. Literature corpora use official test splits when downloaded.",
        },
        "D4": {
            "status": _STATUS_PARTIAL,
            "response": (
                f"This run: entities={len(kg.entities) if kg else 0}, "
                f"relations={len(kg.relations) if kg else 0}. "
                "Literature spike default limit=30 documents/corpus."
            ),
        },
        "D5": {
            "status": _STATUS_PARTIAL,
            "response": "Literature uses published test partitions. Synthetic notes are evaluation-only, no train split.",
        },
        "D6": {
            "status": _STATUS_REPORTED,
            "response": (
                "Regex + optional GLiNER PII. Experimental, not HIPAA. "
                "PII/BII leakage benchmark reports precision, recall, F1, leak rate "
                "(DeepTeam PIILeakage types + business identifiers)."
            ),
        },
        "D7": {
            "status": _STATUS_REPORTED,
            "response": "Synthetic data Apache-2.0 in-repo. NCBI/BC5CDR via public PubTator. DUA corpora stay off git.",
        },
        "D8": {"status": _STATUS_NOT, "response": "No encounter timestamps on synthetic notes."},
        "D9": {
            "status": _STATUS_PARTIAL,
            "response": "Synthetic lexicon is English, adult, common chronic disease. Not representative.",
        },
        "AN1": {
            "status": _STATUS_PARTIAL,
            "response": "Gold in data/synthetic/*.jsonl; NCBI/BC5CDR use corpus guidelines. No in-house annotation manual.",
        },
        "AN2": {"status": _STATUS_NOT, "response": "No human annotation campaign in this repository."},
        "AN3": {"status": _STATUS_NOT, "response": "IAA not measured here; literature corpora report their own IAA."},
        "AN4": {
            "status": _STATUS_PARTIAL,
            "response": "Schema + optional LLM adjudication. No human dual annotation.",
        },
        "AN5": {
            "status": _STATUS_REPORTED,
            "response": "Synthetic gold is in-repo. NCBI Disease and BC5CDR gold via PubTator/public releases.",
        },
        "O1": {
            "status": _STATUS_REPORTED if outcomes else _STATUS_PARTIAL,
            "response": (
                yaml.safe_dump(outcomes, sort_keys=False).strip()
                if outcomes
                else "Entity/relation F1, ontology pass, PHI leak rate, p95 latency, planning $/doc. See docs/evaluation.md."
            ),
        },
        "O2": {
            "status": _STATUS_PARTIAL,
            "response": "Zero-shot CID RelEx did not recover gold pairs; unlinked mentions stay UNLINKED; CAUTION→NEEDS_REVIEW.",
        },
        "O3": {
            "status": _STATUS_PARTIAL,
            "response": "LatencyBudget + estimate_cost_per_document planning model (not a vendor invoice).",
        },
        "O4": {
            "status": _STATUS_PARTIAL,
            "response": "NCBI Disease and BC5CDR spike (examples/run_literature_benchmark.py). Nightly CI is telemetry, not a release gate.",
        },
        "O5": {
            "status": _STATUS_REPORTED,
            "response": (
                "Not a medical device, not HIPAA de-identification, not OWL/SHACL reasoning, "
                "not a Kafka runtime. GLiNER is a sensing tier, not a BioBERT replacement."
            ),
        },
    }
    for key, text in extra.items():
        filled[key] = {"status": _STATUS_REPORTED, "response": text}
    return filled
