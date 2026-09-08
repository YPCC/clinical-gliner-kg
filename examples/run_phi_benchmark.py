#!/usr/bin/env python3
"""PHI / PII cascade benchmark on bundled synthetic notes."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.data import load_synthetic_phi_notes
from clinical_gliner_kg.eval.metrics import normalize

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", default="tag", choices=["tag", "mask", "route"])
    parser.add_argument("--gliner-pii", action="store_true", help="Also load GLiNER PII weights if installed")
    args = parser.parse_args()

    gate = PHIPolicyGate(action=args.action, enable_gliner_pii=args.gliner_pii)
    notes = load_synthetic_phi_notes()

    table = Table(title="Synthetic PHI / PII detection")
    table.add_column("Doc")
    table.add_column("Gold PHI")
    table.add_column("Detected")
    table.add_column("Recall")
    table.add_column("Extra detections")

    hits = 0
    gold_total = 0
    pred_total = 0
    for note in notes:
        findings = gate.detect(note["text"])
        gold = note.get("phi", [])
        gold_norms = {normalize(item["text"]) for item in gold}
        pred_norms = {normalize(item.text) for item in findings}
        # Partial match: gold span contained in a detection or vice versa.
        matched = set()
        for g in gold_norms:
            for p in pred_norms:
                if g in p or p in g:
                    matched.add(g)
                    break
        rec = len(matched) / len(gold_norms) if gold_norms else 1.0
        extra = sorted(p for p in pred_norms if not any(g in p or p in g for g in gold_norms))
        hits += len(matched)
        gold_total += len(gold_norms)
        pred_total += len(pred_norms)
        table.add_row(
            note["id"],
            str(len(gold_norms)),
            str(len(pred_norms)),
            f"{rec:.0%}",
            ", ".join(extra) or "—",
        )
    console.print(table)
    overall = hits / gold_total if gold_total else 1.0
    console.print(
        f"Overall span-recall {overall:.0%}  "
        f"({hits}/{gold_total} gold spans)  predictions={pred_total}  "
        f"backend={'regex+gliner-pii' if args.gliner_pii else 'regex'}"
    )
    console.print(
        "For DUA corpora (n2c2 2006/2014 de-id, MIMIC) download from the official portal "
        "and keep files outside git. Catalog: https://github.com/YPCC/medical-data"
    )


if __name__ == "__main__":
    main()
