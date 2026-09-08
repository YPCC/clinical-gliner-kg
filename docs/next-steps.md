# Next steps — make the implementation match the architecture

Review of the repo against the README (technical spike, not a production clinical platform). This file is the working backlog. Items marked **done in this pass** are already in `main`.

## What we agreed the system *is*

A **semantic extraction control plane**:

GLiNER high-recall sensing → PHI gate → terminology grounding → **schema** (domain-range) validation → confidence router → **selective** LLM adjudication → provenance-bearing assertions → Healthcare KG artifacts.

It is **not** “another BioBERT” and not a certified PHI / HIPAA product.

C4 views: [c4/context.md](c4/context.md) · [c4/container.md](c4/container.md) · [c4/system.md](c4/system.md).

---

## P0 — correctness (done this pass)

These were creating false confidence in the graph.

| Review item | Change |
|---|---|
| LLM `_arbitrate()` was hard-coded rules + confidence bump | Forbidden schema pairs → `REJECTED` with **original** confidence. Ambiguous + no LLM → `NEEDS_REVIEW`. Ambiguous + LLM → `LLM_VALIDATED` / `LLM_REJECTED`. **Never** raise confidence just because a function ran. |
| Entities auto-`VALIDATED` even when unlinked | Catalog/OAK hit → `LINKED` (+ `linking_confidence`). Miss → `UNLINKED`. Extraction score stays on `confidence`. |
| RelEx `_nearest()` first surface string | Bind by **span identity**, then overlap, then unique surface, then closest offset. Repeated “metformin” no longer always attaches to the first mention. |
| PHI `str.replace` + no dedupe | Overlap merge; mask **right-to-left by offsets**. |
| Cypher could `MATCH` a suppressed PHI node | Emitter requires both endpoints in the non-PHI id set. |
| README over-claimed streaming / OWL / LLM | Wording tightened; C4 marks planned vs implemented. |

New statuses: `LINKED`, `UNLINKED`, `NEEDS_REVIEW`, `LLM_VALIDATED`, `LLM_REJECTED`. `ADJUDICATED` is legacy and no longer written.

---

## P1 — make the spike robust (this pass)

| Item | State |
|---|---|
| Assertion-level PROV + decision history + terminology version | **Done** (`DecisionEvent`, `clin:Assertion`, catalog `version`) |
| RelEx span goldens | **Done** (`tests/data/relex_spans.json`) |
| CI-fast vs CI-integration | **Done** (`.github/workflows/ci.yml` heuristic; `ci-integration.yml` RDF goldens + nightly GLiNER 2.5-small) |
| EventEnvelope + JSONL idempotent upsert | **Done** (`examples/run_stream_jsonl.py`) |
| RDFS KG via rdflib + PyLD + SPARQL | **Done** (`graph.target: lpg \| rdfs \| both`) |

---

## P2 — semantics (the differentiated architecture)

| Level | State |
|---|---|
| 1 JSON domain-range | **Now** (`ontology_rules.json`) |
| 2 OAK types + catalog | **Now** (mini OBO; Mondo/ChEBI opt-in) |
| 3 RDF/OWL + SHACL + subclass | Next: compile allow/deny to SHACL; oaklib `ancestors()` so `Metformin rdf:type Ingredient` still satisfies `domain Drug` |
| 4 Patient / temporal constraints | Later: medication start/stop, lab trend, contraindication |

Until Level 3 ships, README must say **schema validation**, not “ontology reasoning”.

---

## P3 — streaming and a living KG (not started)

Replace the README phrase “streaming events” with the honest one (already done): *designed to support event-driven ingestion*.

Then, in order:

1. `EventEnvelope` (doc id, source, observed_at, payload, idempotency key)
2. Worker `process_envelope` → assertion set
3. Upsert/retract against previous hash of `(doc_id, span, relation)`
4. Adapter: Kafka / Pub/Sub / FHIR Subscription (one adapter, not three frameworks)
5. Longitudinal entity resolution (patient, encounter, repeated labs) **before** claiming a continuously evolving KG

---

## P4 — production bar (out of scope for the spike)

- BAA, DUA handling, audit log, key management
- Presidio + clinical PHI model + contextual adjudicator
- Load/latency SLO, ONNX/GPU serving
- Human review UI
- Certified terminology distributions (SNOMED RF2, RxNorm full)

The spike should stay a **research / architecture control plane** until P1+P2 are boringly green.

---

## Suggested sequence (if we only do five more things)

1. SHACL compiled from `ontology_rules.json` + oaklib subclass closure  
2. Assertion PROV on every edge  
3. RelEx span golden tests + NCBI/BC5CDR nightly  
4. `EventEnvelope` + idempotent upsert (even if the “bus” is a directory of JSONL)  
5. Pending-review sink so `NEEDS_REVIEW` never looks like `VALIDATED` in Neo4j

That is the path from “GLiNER → KG demo” to the control plane the review asked for.
