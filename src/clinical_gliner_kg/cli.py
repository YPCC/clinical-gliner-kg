"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline
from clinical_gliner_kg.settings import load_settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cascaded clinical GLiNER → ontology → KG pipeline")
    parser.add_argument("text", nargs="?", help="Clinical text to extract")
    parser.add_argument("--backend", default=None, help="auto | gliner25 | gliner_spacy | heuristic")
    parser.add_argument("--config", type=Path, default=None, help="Path to pipeline.yaml")
    parser.add_argument("--print-config", action="store_true", help="Print resolved settings (secrets redacted) and exit")
    parser.add_argument("--json", action="store_true", help="Print JSON-LD instead of a short summary")
    parser.add_argument("--format", dest="graph_format", default=None, help="lpg | rdfs | both (overrides graph.target)")
    args = parser.parse_args(argv)
    if args.print_config:
        settings = load_settings(args.config)
        print(json.dumps(settings.redacted(), indent=2))
        return
    text = args.text or (
        "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."
    )
    pipeline = ClinicalSemanticExtractionPipeline(backend=args.backend, config_path=args.config)
    if args.graph_format:
        pipeline.settings.graph = pipeline.settings.graph.model_copy(update={"target": args.graph_format})
        pipeline.emitter.settings = pipeline.settings.graph
    kg = pipeline.process_document(text, document_id="cli")
    if args.json:
        print(json.dumps(kg.model_dump(), indent=2, default=str))
        return
    print(
        f"backend={kg.provenance.extraction_backend} target={kg.provenance.graph_target} "
        f"entities={len(kg.entities)} relations={len(kg.relations)}"
    )
    for ent in kg.entities:
        term = f"{ent.terminology.system}:{ent.terminology.code}" if ent.terminology else "-"
        print(f"  ENT {ent.label:18} {ent.text:30} {term} [{ent.validation_status.value}]")
    for rel in kg.relations:
        print(f"  REL {rel.relation:18} {rel.subject_id} -> {rel.object_id} [{rel.validation_status.value}]")
    if kg.cypher_queries:
        print(f"  LPG cypher statements: {len(kg.cypher_queries)}")
    if kg.turtle:
        print(f"  RDFS turtle chars: {len(kg.turtle)}")
    if kg.sparql:
        print(f"  SPARQL treats: {kg.sparql.get('treats')}")


if __name__ == "__main__":
    main()
