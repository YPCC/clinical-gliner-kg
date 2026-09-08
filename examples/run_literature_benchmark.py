#!/usr/bin/env python3
"""Score the cascade on NCBI Disease + BC5CDR and report architecture metrics.

Metrics
-------
entity F1, relation F1, ontology pass rate, PHI recall vs over-redaction,
p95 latency, estimated USD/document.

GLiNER 2.5 is used when installed (`--backend gliner25`). oaklib grounds
unlinked disease/chemical spans via sqlite:obo:mondo / chebi when those
adapters can be opened.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.backends import available_backends
from clinical_gliner_kg.components.ontology_linker import OntologyValidationEngine
from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.data import load_synthetic_phi_notes
from clinical_gliner_kg.data.literature import load_bc5cdr, load_ncbi_disease
from clinical_gliner_kg.eval.benchmark import (
    LatencyBudget,
    estimate_cost_per_document,
    gold_entity_spans,
    kg_entity_spans,
    kg_relations,
    ontology_pass_rate,
    phi_scores,
    timed,
)
from clinical_gliner_kg.eval.metrics import entity_prf, relation_prf
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline

console = Console()

LITERATURE_LABELS = ["disease", "chemical", "condition", "medication"]
LITERATURE_RELATIONS = ["CID", "TREATS", "INDICATES"]


def _score_corpus(name: str, rows: list[dict], pipeline: ClinicalSemanticExtractionPipeline) -> dict:
    pred_ents: list[tuple[str, str]] = []
    gold_ents: list[tuple[str, str]] = []
    pred_rels: list[tuple[str, str, str]] = []
    gold_rels: list[tuple[str, str, str]] = []
    lat = LatencyBudget()
    pass_rates = []
    linked_rates = []
    escalations = 0
    for row in rows:
        kg, seconds = timed(pipeline.process_document, row["text"], document_id=str(row["id"]))
        lat.add(seconds)
        pred_ents.extend(kg_entity_spans(kg))
        gold_ents.extend(gold_entity_spans(row.get("entities") or []))
        pred_rels.extend(kg_relations(kg))
        gold_rels.extend(
            (item.get("subject") or item[0], item.get("relation") or item[1], item.get("object") or item[2])
            if isinstance(item, dict)
            else item
            for item in (row.get("relations") or [])
        )
        rates = ontology_pass_rate(kg)
        pass_rates.append(rates["relation_pass"])
        linked_rates.append(rates["entity_linked"])
        if kg.provenance.escalation_used:
            escalations += 1
    latency = lat.summary()
    escalation_rate = escalations / max(len(rows), 1)
    return {
        "corpus": name,
        "n": len(rows),
        "backend": getattr(pipeline.extractor, "name", "unknown"),
        "entity": entity_prf(pred_ents, gold_ents),
        "relation": relation_prf(pred_rels, gold_rels),
        "ontology_relation_pass": sum(pass_rates) / max(len(pass_rates), 1),
        "ontology_entity_linked": sum(linked_rates) / max(len(linked_rates), 1),
        "latency": latency,
        "cost": estimate_cost_per_document(latency, escalation_rate),
        "oak_adapters": OntologyValidationEngine().oak.available,
    }


def _score_phi() -> dict:
    gate = PHIPolicyGate(action="tag")
    pred: list[str] = []
    gold: list[str] = []
    for note in load_synthetic_phi_notes():
        pred.extend(item.text for item in gate.detect(note["text"]))
        gold.extend(item["text"] for item in note.get("phi") or [])
    return phi_scores(pred, gold)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--limit", type=int, default=80, help="Docs per corpus (default 80 for a short spike)")
    parser.add_argument("--split", default="test")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    console.print(f"Available backends: {available_backends()}")
    pipeline = ClinicalSemanticExtractionPipeline(
        backend=args.backend,
        labels=LITERATURE_LABELS,
        relations=LITERATURE_RELATIONS,
        enable_relations=True,
    )
    console.print(f"Using backend={pipeline.extractor.name}")

    results = []
    try:
        ncbi = load_ncbi_disease(split=args.split, limit=args.limit)
        console.print(f"NCBI Disease {args.split}: {len(ncbi)} docs")
        results.append(_score_corpus("ncbi_disease", ncbi, pipeline))
    except Exception as exc:
        console.print(f"[red]NCBI Disease load/score failed: {exc}[/red]")

    try:
        bc5 = load_bc5cdr(split=args.split, limit=args.limit)
        console.print(f"BC5CDR {args.split}: {len(bc5)} docs")
        results.append(_score_corpus("bc5cdr", bc5, pipeline))
    except Exception as exc:
        console.print(f"[red]BC5CDR load/score failed: {exc}[/red]")

    phi = _score_phi()

    table = Table(title="Literature spike: entity / relation / ontology / cost")
    table.add_column("Corpus")
    table.add_column("N")
    table.add_column("Ent F1")
    table.add_column("Ent P/R")
    table.add_column("Rel F1")
    table.add_column("Ont pass")
    table.add_column("Linked")
    table.add_column("P95 s")
    table.add_column("$ / doc")
    table.add_column("$ / 100k")
    for row in results:
        table.add_row(
            row["corpus"],
            str(row["n"]),
            f"{row['entity']['f1']:.3f}",
            f"{row['entity']['precision']:.2f}/{row['entity']['recall']:.2f}",
            f"{row['relation']['f1']:.3f}",
            f"{row['ontology_relation_pass']:.2f}",
            f"{row['ontology_entity_linked']:.2f}",
            f"{row['latency']['p95']:.3f}",
            f"{row['cost']['usd_per_doc']:.6f}",
            f"{row['cost']['usd_per_100k']:.2f}",
        )
    console.print(table)
    console.print(
        f"PHI recall={phi['recall']:.2f}  over-redaction={phi['over_redaction']:.2f}  "
        f"(synthetic PHI notes; names need GLiNER PII)"
    )
    if results:
        console.print(f"oaklib adapters opened: {results[0]['oak_adapters'] or 'none (catalog fallback)'}")
        console.print(
            "Cost model: CPU-hour=$0.40 plus $0.012 only on LLM-escalated docs. "
            "Local GLiNER has no token bill."
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"results": results, "phi": phi}, indent=2), encoding="utf-8")
        console.print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
