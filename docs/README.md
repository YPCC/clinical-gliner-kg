# Documentation

**clinical-gliner-kg** is a *provenance-aware semantic extraction and validation control plane* for healthcare knowledge generation — a research / reference implementation, not an enterprise production platform.

Thesis (what the code is becoming):

**GLiNER sensing → PHI policy → terminology grounding → semantic validation → confidence routing → selective LLM adjudication → provenance-bearing assertions → LPG/RDF healthcare KG**

| Page | What it covers |
|---|---|
| [Status vs next](next-steps.md) | **Shipped vs pending** after the 2026-09-08 review |
| [Configuration](configuration.md) | YAML; Gemini / OpenAI-compat keys; Vertex ADC; `graph.target` |
| [Graph (LPG / RDFS)](graph.md) | Cypher vs rdflib+PyLD SPARQL; JSONL upsert |
| [Overview](overview.md) | Purpose, non-goals |
| [Architecture](architecture.md) | Cascade stages |
| [C4 diagrams](c4/README.md) | Context, container, system |
| [oaklib grounding](oaklib-grounding.md) | Local OBO / SQLite vs OLS/BioPortal |
| [CINEX report](cinex.md) | 29-item study JSON (https://www.cinex-guideline.org/) |
| [Evaluation](evaluation.md) | NCBI / BC5CDR; **PII/BII leak rate**, P/R/F1 |
| [Data policy](data-policy.md) | Open corpora vs DUA |
| [Bibliography](bibliography.md) | Papers, software, ontologies |
| [Infographics](infographics.md) | Cascade + cost visuals |
| [LinkedIn post](linkedin-post.md) | Draft |

---

## Shipped (new since the first review)

These were the defects that created false confidence. They are in `main`.

| Area | Now |
|---|---|
| README honesty | Streaming, OWL, LLM, and PHI are described as designed-for / experimental, not production |
| LLM adjudication | Real `chat_complete()` when a provider is configured. No confidence inflation. `CAUTION` → `NEEDS_REVIEW` (not accept) |
| Entity status | `LINKED` / `UNLINKED` — unlinked spans are not stamped `VALIDATED` |
| RelEx | Bind by **character span**; golden test for repeated “metformin” |
| PHI | Offset mask, overlap dedupe; emitter drops PHI endpoints |
| Assertion PROV | `clin:Assertion` + `DecisionEvent` history + catalog `version` |
| Graphs | `graph.target: lpg \| rdfs \| both` — Cypher **and** RDFS/SPARQL (rdflib + PyLD) |
| Events | `EventEnvelope` + idempotent JSONL store (not Kafka) |
| CI | Fast heuristic gate; integration workflow for RDF/spans/store; nightly GLiNER 2.5-small is **telemetry** (`continue-on-error`), not a release gate |

Config: [`config/pipeline.yaml`](../config/pipeline.yaml). C4: [context](c4/context.md) · [container](c4/container.md) · [system](c4/system.md).

---

## Pending (next, in review order)

RDFS **infers** types; it does **not** reject illegal triples. That is why SHACL is next, not more properties.

| # | Work | Why |
|---|---|---|
| 1 | **SHACL** beside RDFS | Validation/rejection ≠ RDFS domain/range inference |
| 2 | **Mention → Concept → Assertion** | Spans are still treated as entities; need mention vs RxNorm concept vs assertion |
| 3 | **Clinical events / time** | `TAKES` is too thin; MedicationAdministration, LabObservation, DiagnosisEvent |
| 4 | Cross-document **entity resolution** | Patient/encounter/lab identity before a living KG |
| 5 | **FHIR** resource/event ingestion | Before Kafka/Pub/Sub infrastructure |
| 6 | **Review queue/API** for `NEEDS_REVIEW` | Status exists; no human workflow |
| 7 | Terminology **edition/date** (SNOMED RF2, RxNorm release, LOINC) | Catalog `version` is a slice label, not an official release |
| 8 | **LLM-adjudication eval** separate from GLiNER NER F1 | Router quality is unmeasured |
| 9 | PHI: Presidio + clinical PHI + FN-first metrics | Keep labeling the current gate experimental |
| 10 | Then Kafka / Pub/Sub / FHIR Subscription adapters | Envelope exists; no bus |

Detail and suggested sequence: [next-steps.md](next-steps.md).

---

## What this is not

Not a BioBERT replacement, not a HIPAA de-identification product, not a stream-processing platform, not OWL/SHACL reasoning yet.

Code: [`src/clinical_gliner_kg/`](../src/clinical_gliner_kg/). Demos: [`examples/`](../examples/).
