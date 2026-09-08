#!/usr/bin/env python3
"""Build a small provenance-aware KG from bundled synthetic notes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from clinical_gliner_kg.data import load_synthetic_clinical_notes
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="heuristic")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--outdir", type=Path, default=Path("outputs/kg"))
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    pipeline = ClinicalSemanticExtractionPipeline(backend=args.backend, config_path=args.config)
    combined_cypher: list[str] = []
    combined_ttl: list[str] = []
    docs = []
    for note in load_synthetic_clinical_notes():
        kg = pipeline.process_document(note["text"], document_id=note["id"])
        docs.append(kg.model_dump())
        combined_cypher.extend(kg.cypher_queries)
        combined_ttl.append(kg.turtle)

    (args.outdir / "graph.json").write_text(json.dumps(docs, indent=2), encoding="utf-8")
    (args.outdir / "graph.cypher").write_text("\n".join(combined_cypher) + "\n", encoding="utf-8")
    (args.outdir / "graph.ttl").write_text("\n".join(combined_ttl), encoding="utf-8")
    print(f"Wrote {args.outdir}/graph.json, graph.cypher, graph.ttl")
    print(f"Documents={len(docs)} cypher_statements={len(combined_cypher)}")


if __name__ == "__main__":
    main()
