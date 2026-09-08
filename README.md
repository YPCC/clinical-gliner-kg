# Clinical-GLiNER-KG

Cascaded clinical extraction plane:

**GLiNER 2.5 → PHI gate → SNOMED/RxNorm/LOINC → spaCy-LLM only when needed → provenance-aware KG**

[![CI](https://github.com/YPCC/clinical-gliner-kg/actions/workflows/ci.yml/badge.svg)](https://github.com/YPCC/clinical-gliner-kg/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

1. **GLiNER turns clinical text into structured entities + relationships** — without sending every document to an LLM.
2. **Use it as a fast, high-recall extraction layer** for NER, PHI/PII, streaming events, and KG triples.
3. **Ground outputs with SNOMED CT, UMLS, RxNorm, LOINC** and healthcare domain models to improve precision.
4. **Escalate only ambiguous cases to an LLM** — improving accuracy while controlling latency, cost, and risk.
5. **Result:** a continuously enriched, provenance-aware Healthcare Knowledge Graph for RAG, analytics, and AI agents.

Footer: [GLiNER 2.5](https://github.com/fastino-ai/GLiNER2) · [Long-context demo](https://huggingface.co/spaces/fastino/gliner25-long-context) · [Classic GLiNER](https://github.com/urchade/GLiNER) · [gliner-spacy](https://github.com/theirstory/gliner-spacy) · [spaCy-LLM](https://github.com/explosion/spacy-llm) · [NAACL paper](https://aclanthology.org/2024.naacl-long.300/) · [Medical data catalog](https://github.com/YPCC/medical-data)

---

## Why a cascade, not “another NER model”

GLiNER 2.5 (Fastino boundary architecture) predicts entity spans directly, supports long context, joint entity–relation decoding, PII checkpoints, and CPU/ONNX-style deployment. That makes it a **lightweight semantic sensing tier** between raw notes / FHIR events and expensive domain models or LLMs.

```
Unstructured / streaming clinical text
        │
        ▼
[1] GLiNER 2.5 + RelEx / gliner-spacy     high-recall candidates
        │
        ▼
[2] PHI / PII policy gate                 regex → GLiNER PII → policy
        │
        ▼
[3] Domain semantics                      RxNorm / SNOMED CT / LOINC
        │                                 domain-range constraints
        ▼
[4] Confidence router
   ├── high-confidence, valid ──────────────────────────┐
   └── low-confidence or illegal relation               │
                    │                                   │
                    ▼                                   │
           [5] spaCy-LLM adjudication                   │
                    │                                   │
                    └────────────────┬──────────────────┘
                                     ▼
                    [6] Provenance-aware KG
                        Cypher · JSON-LD · Turtle
```

Reference sentence:

> Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%.

Derived graph (after grounding + constraints):

| Subject | Relation | Object | Grounding |
|---|---|---|---|
| Patient | `HAS_CONDITION` | type 2 diabetes | SNOMED CT `44054006` |
| Patient | `TAKES` | metformin | RxNorm `6809` |
| metformin | `TREATS` | type 2 diabetes | allowed domain-range |
| HbA1c | `HAS_VALUE` | 8.2% | LOINC `4548-4` |

A spurious candidate such as `metformin HAS_ANATOMICAL_SITE kidney` is **rejected** by ontology rules and never written to the graph.

---

## Repository map

```
clinical-gliner-kg/
├── config/                 pipeline.yaml, ontology rules, terminology catalog, spaCy-LLM cfg
├── src/clinical_gliner_kg/
│   ├── backends/           GLiNER 2.5 · gliner-spacy · heuristic fallback
│   ├── components/         PHI gate · ontology linker · LLM adjudicator
│   ├── graph/              Cypher / JSON-LD / Turtle emitter
│   └── pipeline.py         cascade orchestrator
├── data/
│   ├── synthetic/          runnable gold notes + PHI examples
│   └── catalogs/           slice of YPCC/medical-data (open vs DUA)
├── examples/               demos and benchmarks
└── tests/                  no-weight unit tests
```

---

## Install

Minimal path (heuristic backend, tests, demos — no model download):

```bash
git clone https://github.com/YPCC/clinical-gliner-kg.git
cd clinical-gliner-kg
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Full showcase stack (GLiNER 2.5, gliner-spacy, spaCy-LLM, RDF):

```bash
pip install -e ".[all]"
# or
pip install -r requirements-full.txt
```

Copy `.env.example` and set keys only if you want live spaCy-LLM or the Fastino hosted client.

| Extra | What it enables |
|---|---|
| `gliner2` | Fastino `AutoExtractor` / `JointIE` on `fastino/gliner2.5-small-v1` (default) or `base` / `multi` |
| `gliner` | Classic `gliner` + spaCy factory `gliner_spacy` |
| `llm` | `spacy-llm` NER.v3 adjudication when `OPENAI_API_KEY` is set |
| `graph` | networkx + rdflib extras |

Backend selection (`--backend` or `CLINICAL_GLINER_BACKEND`):

- `auto` — GLiNER 2.5 if installed, else gliner-spacy, else heuristic
- `gliner25` — Fastino GLiNER 2.5
- `gliner_spacy` — spaCy component wrapping urchade GLiNER
- `heuristic` — lexicon / pattern fallback used by CI

---

## Run

```bash
# Architect reference sentence
python examples/run_pipeline.py --backend heuristic

# All bundled synthetic notes
python examples/run_pipeline.py --backend heuristic --all-notes

# PHI / PII cascade on synthetic identifiers
python examples/run_phi_benchmark.py

# Emit Cypher + Turtle KG
python examples/run_kg_demo.py --outdir outputs/kg

# Live quality on bundled gold + planning matrix
python examples/run_architecture_spike.py --backend heuristic

# Catalog of open vs DUA evaluation sets
python examples/list_open_datasets.py

# One-liner CLI
clinical-gliner "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."
```

After installing the full stack:

```bash
python examples/run_pipeline.py --backend gliner25
python examples/run_pipeline.py --backend gliner_spacy
python examples/run_phi_benchmark.py --gliner-pii
```

---

## Benchmarks and data policy

This repo **does not ship n2c2, i2b2, or MIMIC notes**. Those corpora require a Data Use Agreement and must not be pushed to GitHub. The parent index is [YPCC/medical-data](https://github.com/YPCC/medical-data).

| Dataset | Access | Role here |
|---|---|---|
| Bundled synthetic clinical notes | open | default NER / RE / KG demo |
| Bundled synthetic PHI notes | open | default PHI gate benchmark |
| [ASQ-PHI](https://data.mendeley.com/datasets/csz5dzp7nx/1) | open (MIT, synthetic) | recommended extra PHI set |
| [NCBI Disease](https://www.ncbi.nlm.nih.gov/research/bionlp/Data/disease/) | open | literature disease NER |
| [BC5CDR](https://biocreative.bioinformatics.udel.edu/tasks/biocreative-v/track-3-cdr/) | open | chemical / disease NER + relations |
| [BioRED](https://ftp.ncbi.nlm.nih.gov/pub/lu/BC8-BioRED-track/) | open | document-level triples |
| n2c2 / i2b2 de-id and concept tasks | DUA | official portal only |
| MIMIC-III / IV | DUA / PhysioNet | official portal only |

`examples/run_architecture_spike.py` measures **live** precision/recall on the bundled gold set. The all-LLM vs GLiNER vs cascade cost/latency table is an **operations planning matrix**, not a vendor invoice. Re-run with `--backend gliner25` on NCBI Disease / BC5CDR locally once those files are downloaded.

Suggested official metrics for a later spike: entity P/R/F1, relation F1, graph-validity rate (ontology pass %), terminology-link accuracy, PHI recall + over-redaction, p95 latency, docs/sec, cost/document.

---

## PHI / PII path

```
Regex / deterministic detectors
        → GLiNER PII checkpoint (optional: fastino/gliner2-privacy-filter-PII-multi)
        → policy action: tag | mask | route
        → HIPAA policy controls before any downstream store or LLM call
```

The graph emitter drops PHI nodes and rejected relations so identifiers do not leak into Cypher or Turtle artifacts.

---

## Provenance written on every assertion

- source document id and character offsets
- extracting backend / checkpoint name
- confidence
- terminology system + code when linked
- validation status: `VALIDATED` · `ESCALATED_TO_LLM` · `ADJUDICATED` · `REJECTED`

---

## Architecture notes

GLiNER 2.5 uses a boundary decoder rather than enumerating bounded candidate spans, which is the reason long-span clinical entities and long notes are in scope. Joint IE (`gliner2.joint_ie.JointIE`) is used when the installed checkpoint exposes it; otherwise entity extraction and `extract_relations` run as two calls on the same `AutoExtractor`.

spaCy remains the orchestration surface: blank `en` pipeline, `gliner_spacy` factory for classic checkpoints, `spacy-llm` `NER.v3` only on the escalation branch.

This is a reference implementation for a technical spike, not a certified medical device and not a HIPAA compliance program.

---

## License

Apache 2.0. Model weights keep their upstream licenses (GLiNER / Fastino Apache 2.0 at time of writing — verify before redistribution).
