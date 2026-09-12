#!/usr/bin/env python3
"""PHI / PII cascade benchmark on bundled synthetic notes."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.data import load_synthetic_phi_notes
from clinical_gliner_kg.eval.leakage import aggregate, score_case

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
    table.add_column("P")
    table.add_column("R")
    table.add_column("F1")
    table.add_column("Leak")

    cases = []
    for note in notes:
        out_text, _ents, findings = gate.apply(note["text"], [])
        scored = score_case(
            gold=note.get("phi") or [],
            pred_spans=[item.text for item in findings],
            original_text=note["text"],
            output_text=out_text,
            action=args.action,
            leakage_type=note.get("leakage_type", "direct_disclosure"),
        )
        cases.append(scored)
        table.add_row(
            note["id"],
            str(scored["n_gold"]),
            str(scored["n_pred"]),
            f"{scored['precision']:.2f}",
            f"{scored['recall']:.2f}",
            f"{scored['f1']:.2f}",
            f"{scored['leak_rate']:.0%}",
        )
    console.print(table)
    summary = aggregate(cases)
    console.print(
        f"P={summary['precision']:.3f}  R={summary['recall']:.3f}  F1={summary['f1']:.3f}  "
        f"leak_rate={summary['leak_rate']:.3f}  over_redaction={summary['over_redaction']:.3f}  "
        f"deepteam_pass_rate={summary['deepteam_pass_rate']:.3f}  "
        f"backend={'regex+gliner-pii' if args.gliner_pii else 'regex'}"
    )
    console.print("Full PII/BII + DeepTeam types: python examples/run_pii_leakage_benchmark.py --action mask")
    console.print(
        "For DUA corpora (n2c2 2006/2014 de-id, MIMIC) download from the official portal "
        "and keep files outside git. Catalog: https://github.com/YPCC/medical-data"
    )


if __name__ == "__main__":
    main()
