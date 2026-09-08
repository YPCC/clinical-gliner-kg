"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import json

from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cascaded clinical GLiNER → ontology → KG pipeline")
    parser.add_argument("text", nargs="?", help="Clinical text to extract")
    parser.add_argument("--backend", default="auto", help="auto | gliner25 | gliner_spacy | heuristic")
    parser.add_argument("--json", action="store_true", help="Print JSON-LD instead of a short summary")
    args = parser.parse_args(argv)
    text = args.text or (
        "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."
    )
    pipeline = ClinicalSemanticExtractionPipeline(backend=args.backend)
    kg = pipeline.process_document(text, document_id="cli")
    if args.json:
        print(json.dumps(kg.model_dump(), indent=2))
        return
    print(f"backend={kg.provenance.extraction_backend} entities={len(kg.entities)} relations={len(kg.relations)}")
    for ent in kg.entities:
        term = f"{ent.terminology.system}:{ent.terminology.code}" if ent.terminology else "-"
        print(f"  ENT {ent.label:18} {ent.text:30} {term}")
    for rel in kg.relations:
        print(f"  REL {rel.relation:18} {rel.subject_id} -> {rel.object_id} [{rel.validation_status.value}]")


if __name__ == "__main__":
    main()
