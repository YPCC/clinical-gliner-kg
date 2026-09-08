# What this repo is

**clinical-gliner-kg** is a reference implementation of a *clinical extraction plane*:

**GLiNER 2.5 → PHI gate → oaklib + terminology catalog → spaCy-LLM only when needed → provenance-aware knowledge graph**

It is software for a technical spike, not a product, not a certified medical device, and not a HIPAA compliance program.

## The claim

Most clinical notes do not need an LLM on every token. A small, zero-shot encoder (GLiNER 2.5) can emit entity and relation candidates. A **local** ontology layer (oaklib over OBO / SQLite files, plus a small RxNorm / SNOMED / LOINC catalog) can ground and reject illegal triples. An LLM is the exception handler.

## What you can run today

- Heuristic backend (CI, no weights)
- Fastino `fastino/gliner2.5-small-v1` when `gliner2[local]` is installed
- Classic GLiNER via `gliner-spacy`
- PHI regex gate; optional GLiNER PII checkpoint
- oaklib `simpleobo:` on the bundled mini ontology, or `sqlite:obo:mondo` / `chebi` when you opt in
- Cypher, JSON-LD, and Turtle emitters
- NCBI Disease + BC5CDR literature spike (`examples/run_literature_benchmark.py`)

## What this is not

- A replacement for BioBERT / PubMedBERT leaderboard numbers
- A license to ship n2c2, i2b2, or MIMIC notes
- A hosted extraction API
- Production PHI de-identification

## Companion repos

- [YPCC/clinical-gliner-kg](https://github.com/YPCC/clinical-gliner-kg) — this code
- [YPCC/medical-data](https://github.com/YPCC/medical-data) — open vs DUA dataset catalog
