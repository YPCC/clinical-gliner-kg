#!/usr/bin/env python3
"""Architecture spike on bundled gold notes.

Reports entity/relation quality for the local cascade. Cost/latency rows for
all-LLM vs GLiNER vs cascade are planning estimates, not live vendor billing.
"""

from __future__ import annotations

import argparse
import time

from pathlib import Path

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.data import load_gold_annotations, load_synthetic_clinical_notes
from clinical_gliner_kg.eval.metrics import entity_prf, entity_prf_by_label, relation_prf
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline

console = Console()


def live_quality(backend: str, config_path: Path | None = None) -> dict:
    notes = {row["id"]: row for row in load_synthetic_clinical_notes()}
    gold = {row["id"]: row for row in load_gold_annotations()}
    pipeline = ClinicalSemanticExtractionPipeline(backend=backend, config_path=config_path)
    pred_ents: list[tuple[str, str]] = []
    gold_ents: list[tuple[str, str]] = []
    pred_rels: list[tuple[str, str, str]] = []
    gold_rels: list[tuple[str, str, str]] = []
    t0 = time.perf_counter()
    for doc_id, note in notes.items():
        kg = pipeline.process_document(note["text"], document_id=doc_id)
        pred_ents.extend((ent.text, ent.label) for ent in kg.entities if not ent.is_phi)
        id_to_text = {ent.id: ent.text for ent in kg.entities}
        pred_rels.extend(
            (
                id_to_text.get(rel.subject_id, rel.subject_id),
                rel.relation,
                id_to_text.get(rel.object_id, rel.object_id),
            )
            for rel in kg.relations
            if rel.validation_status.value != "REJECTED"
        )
        g = gold[doc_id]
        gold_ents.extend((text, label) for text, label in g["entities"])
        gold_rels.extend((s, r, o) for s, r, o in g["relations"])
    elapsed = time.perf_counter() - t0
    return {
        "backend": getattr(pipeline.extractor, "name", backend),
        "seconds": elapsed,
        "entity": entity_prf(pred_ents, gold_ents),
        "by_label": entity_prf_by_label(pred_ents, gold_ents),
        "relation": relation_prf(pred_rels, gold_rels),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="heuristic")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    quality = live_quality(args.backend, args.config)
    console.print(
        f"[bold]Live cascade on synthetic gold[/bold]  backend={quality['backend']}  "
        f"time={quality['seconds']:.3f}s"
    )

    live = Table(title="Entity / relation quality (exact-span, bundled gold)")
    live.add_column("Task")
    live.add_column("P")
    live.add_column("R")
    live.add_column("F1")
    live.add_row(
        "Entities",
        f"{quality['entity']['precision']:.2f}",
        f"{quality['entity']['recall']:.2f}",
        f"{quality['entity']['f1']:.2f}",
    )
    live.add_row(
        "Relations",
        f"{quality['relation']['precision']:.2f}",
        f"{quality['relation']['recall']:.2f}",
        f"{quality['relation']['f1']:.2f}",
    )
    console.print(live)

    by_label = Table(title="Entity F1 by label")
    by_label.add_column("Label")
    by_label.add_column("P")
    by_label.add_column("R")
    by_label.add_column("F1")
    for label, scores in quality["by_label"].items():
        by_label.add_row(label, f"{scores['precision']:.2f}", f"{scores['recall']:.2f}", f"{scores['f1']:.2f}")
    console.print(by_label)

    plan = Table(title="Planning matrix (illustrative operations estimates, not a live bill)")
    plan.add_column("Architecture")
    plan.add_column("Throughput")
    plan.add_column("P95 latency")
    plan.add_column("Entity recall")
    plan.add_column("Relation prec.")
    plan.add_column("Cost / 100k docs")
    plan.add_column("PHI surface")
    plan.add_column("Governance")
    plan.add_row(
        "All-to-LLM",
        "low",
        "high",
        "high",
        "medium-high",
        "high (token billing)",
        "external API",
        "prompt-only",
    )
    plan.add_row(
        "Standalone GLiNER 2.5",
        "high",
        "low",
        "high",
        "medium",
        "compute only",
        "local",
        "limited constraints",
    )
    plan.add_row(
        "Cascade (this repo)",
        "high",
        "low, spikes on escalate",
        "high",
        "high after ontology",
        "mostly compute",
        "local PHI gate",
        "ontology + provenance",
    )
    console.print(plan)
    console.print(
        "Measure real GLiNER 2.5 / spaCy-LLM numbers with `--backend gliner25` after "
        "`pip install -r requirements-full.txt`. Open literature sets (NCBI Disease, BC5CDR) "
        "and DUA clinical sets are listed in data/catalogs/medical_data_index.yaml."
    )


if __name__ == "__main__":
    main()
