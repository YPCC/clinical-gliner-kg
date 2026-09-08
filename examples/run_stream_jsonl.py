#!/usr/bin/env python3
"""Ingest synthetic notes as EventEnvelopes into the JSONL assertion store."""

from __future__ import annotations

import argparse
from pathlib import Path

from clinical_gliner_kg.data import load_synthetic_clinical_notes
from clinical_gliner_kg.graph.store import JsonlGraphStore
from clinical_gliner_kg.models import EventEnvelope
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="heuristic")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--store", type=Path, default=Path("outputs/kg/assertions.jsonl"))
    args = parser.parse_args()

    pipeline = ClinicalSemanticExtractionPipeline(backend=args.backend, config_path=args.config)
    store = JsonlGraphStore(args.store)
    for note in load_synthetic_clinical_notes():
        env = EventEnvelope(document_id=note["id"], payload=note["text"], source="synthetic")
        kg = pipeline.process_and_upsert(env, store)
        print(f"{note['id']}: entities={len(kg.entities)} relations={len(kg.relations)} key={env.key()}")
    live = store.load()
    print(f"store={args.store} live_assertions={len(live)}")


if __name__ == "__main__":
    main()
