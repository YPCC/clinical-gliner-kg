#!/usr/bin/env python3
"""Run the cascaded pipeline on the architect reference sentence and bundled notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from clinical_gliner_kg.data import load_synthetic_clinical_notes
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline

console = Console()


def render_kg(kg) -> None:
    ent_table = Table(title="Extracted & grounded entities")
    ent_table.add_column("ID", style="dim")
    ent_table.add_column("Span")
    ent_table.add_column("Label", style="green")
    ent_table.add_column("Conf", justify="right")
    ent_table.add_column("Terminology", style="cyan")
    ent_table.add_column("PHI")
    for ent in kg.entities:
        term = (
            f"{ent.terminology.system}:{ent.terminology.code} ({ent.terminology.display})"
            if ent.terminology
            else "—"
        )
        ent_table.add_row(ent.id, ent.text, ent.label, f"{ent.confidence:.2f}", term, "yes" if ent.is_phi else "")
    console.print(ent_table)

    rel_table = Table(title="Relations after ontology + adjudication")
    rel_table.add_column("Subject")
    rel_table.add_column("Relation", style="yellow")
    rel_table.add_column("Object")
    rel_table.add_column("Status")
    rel_table.add_column("Comment")
    for rel in kg.relations:
        rel_table.add_row(
            rel.subject_id,
            rel.relation,
            rel.object_id,
            rel.validation_status.value,
            rel.validation_comment or "",
        )
    console.print(rel_table)
    console.print("\n[bold]Cypher mutations[/bold]")
    for query in kg.cypher_queries:
        console.print(f"  {query.replace('[', '\\[')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="heuristic")
    parser.add_argument("--all-notes", action="store_true")
    parser.add_argument("--dump-json", type=Path)
    args = parser.parse_args()

    pipeline = ClinicalSemanticExtractionPipeline(backend=args.backend)
    if args.all_notes:
        notes = load_synthetic_clinical_notes()
    else:
        notes = [
            {
                "id": "ENC_2026_0908",
                "text": "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%.",
            }
        ]

    payloads = []
    for note in notes:
        console.print(Panel(note["text"], title=f"{note['id']}  backend={pipeline.extractor.name}"))
        kg = pipeline.process_document(note["text"], document_id=note["id"])
        render_kg(kg)
        payloads.append(kg.model_dump())

    if args.dump_json:
        args.dump_json.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
        console.print(f"Wrote {args.dump_json}")


if __name__ == "__main__":
    main()
