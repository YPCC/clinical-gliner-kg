#!/usr/bin/env python3
"""PII / BII leakage benchmark (DeepTeam types + precision / recall / F1 / leak rate).

DeepTeam PIILeakage: https://trydeepteam.com/docs/red-teaming-vulnerabilities-pii-leakage
Types: direct_disclosure, api_and_database_access, session_leak, social_manipulation.

BII = business identifiable information (accounts, contract IDs, internal tickets),
reported as a separate family. Not defined on the DeepTeam page.

Leak rate = gold identifier spans still readable in the *output* (mask) or missed
by the detector (tag). Lower is better. deepteam_pass_rate is the case-level
binary (1 = no leak).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.data import load_synthetic_phi_notes
from clinical_gliner_kg.eval.leakage import aggregate, score_case
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline
from clinical_gliner_kg.report.cinex import build_cinex_report

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", default="mask", choices=["tag", "mask", "route"])
    parser.add_argument("--gliner-pii", action="store_true")
    parser.add_argument("--cinex", action="store_true", help="Write a CINEX JSON alongside the scores")
    parser.add_argument("--outdir", type=Path, default=Path("outputs/eval"))
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    gate = PHIPolicyGate(action=args.action, enable_gliner_pii=args.gliner_pii)
    notes = load_synthetic_phi_notes()
    cases = []
    table = Table(title=f"PII / BII leakage  action={args.action}")
    table.add_column("Doc")
    table.add_column("Type")
    table.add_column("Fam")
    table.add_column("P")
    table.add_column("R")
    table.add_column("F1")
    table.add_column("Leak")
    table.add_column("DT")

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
        scored["id"] = note["id"]
        cases.append(scored)
        table.add_row(
            note["id"],
            scored["leakage_type"][:18],
            ",".join(scored["families"]),
            f"{scored['precision']:.2f}",
            f"{scored['recall']:.2f}",
            f"{scored['f1']:.2f}",
            f"{scored['leak_rate']:.2f}",
            "pass" if scored["deepteam_score"] else "FAIL",
        )

    summary = aggregate(cases)
    console.print(table)
    console.print(
        f"micro P={summary['precision']:.3f}  R={summary['recall']:.3f}  F1={summary['f1']:.3f}  "
        f"leak_rate={summary['leak_rate']:.3f}  doc_leak_rate={summary['doc_leak_rate']:.3f}  "
        f"over_redaction={summary['over_redaction']:.3f}  "
        f"deepteam_pass_rate={summary['deepteam_pass_rate']:.3f}  "
        f"({summary['n_leaked']}/{summary['n_gold']} gold spans leaked)"
    )
    for family, row in summary["by_family"].items():
        console.print(f"  family {family:4} leak_rate={row['leak_rate']:.3f} pass={row['deepteam_pass_rate']:.3f} n={row['n_docs']}")
    for kind, row in summary["by_type"].items():
        console.print(f"  type   {kind:24} leak_rate={row['leak_rate']:.3f} pass={row['deepteam_pass_rate']:.3f}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "cases": cases, "action": args.action}
    (args.outdir / "pii_bii_leakage.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.cinex:
        pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic", config_path=args.config)
        kg = pipeline.process_document("CINEX leakage study cover.", document_id="pii_bii")
        cinex = build_cinex_report(kg, pipeline.settings, outcomes={"pii_bii_leakage": summary})
        (args.outdir / "cinex.json").write_text(json.dumps(cinex, indent=2), encoding="utf-8")
        console.print(f"Wrote {args.outdir}/cinex.json  reported={cinex['completeness']['reported']}/29")
    console.print(
        "DeepTeam binary is case-level; leak_rate is span-level (privacy-first). "
        "This is an experimental gate, not a HIPAA program."
    )


if __name__ == "__main__":
    main()
