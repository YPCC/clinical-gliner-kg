# Status and next steps

Working backlog after the **2026-09-08** architecture review. Research / reference control plane, not enterprise production (~8/10 as a spike, ~5/10 as a deployable clinical system).

Thesis to preserve:

**GLiNER sensing → PHI policy → terminology grounding → semantic validation → confidence routing → selective LLM adjudication → provenance-bearing assertions → LPG/RDF healthcare KG**

The differentiator is **governance of semantic assertions**, not GLiNER itself.

---

## Shipped

### P0 — false confidence (done)

| Was | Now |
|---|---|
| Heuristic “adjudication” + confidence bump | Real LLM or `NEEDS_REVIEW`; original score kept |
| Unlinked entity → `VALIDATED` | `LINKED` / `UNLINKED` |
| RelEx first surface string | Span identity (`tests/data/relex_spans.json`) |
| PHI `str.replace` | Offset mask + overlap merge |
| Cypher to PHI nodes | Both endpoints must be non-PHI |
| README over-claim | Streaming / OWL / LLM / PHI wording is honest |

LLM tokens: `ACCEPT` → `LLM_VALIDATED`, `REJECT` → `LLM_REJECTED`, **`CAUTION` → `NEEDS_REVIEW`** (not accept).

### P1 — control-plane foundations (done)

| Item | Where |
|---|---|
| Assertion PROV + decision history | `DecisionEvent`, `clin:Assertion` |
| LPG **and** RDFS | `graph.target: lpg \| rdfs \| both` — [graph.md](graph.md) |
| Event envelope + JSONL upsert | `EventEnvelope`, `JsonlGraphStore` |
| CI-fast vs CI-integration | Heuristic is the **gate**. Nightly GLiNER NCBI/BC5CDR is **telemetry** (`continue-on-error`) — do not treat it as a release quality gate |

RDFS domain/range is on disk. That is **inference**, not **constraint**. Illegal triples are still rejected by JSON `ontology_rules.json`, not by RDFS.

---

## Pending — do these next, in this order

The review’s priority list, mapped to work.

### 1. SHACL validation alongside RDFS (P2)

Keep two layers:

- **RDFS/OWL** — infer `rdf:type` (Medication ⊑ ClinicalEntity, …)
- **SHACL** — reject `Medication HAS_ANATOMICAL_SITE Anatomy`

Compile `config/ontology_rules.json` → SHACL shapes; run pyshacl on the rdflib graph; failed shapes → `REJECTED` with the shape id in `DecisionEvent`. oaklib `ancestors()` so `Metformin rdf:type Ingredient` still satisfies `domain Drug`.

Until this ships, say **schema validation**, not ontology reasoning.

### 2. Mention → Concept → Assertion (biggest semantic gap)

Today a span *is* the entity. Split:

```
TEXT MENTION     "metformin"  span 124–133  note N
      ↓ grounding
CONCEPT          RxNorm:6809  version 2026-03
      ↓
ASSERTION        Patient TAKES Concept     time T1  provenance …
```

Needed for duplicate mentions, multi-document aggregation, contradiction, and temporal reasoning. RelEx spans get you to Mention; they do not get you to Concept.

### 3. Clinical events / time before more relation types

`Patient TAKES Metformin` is too thin. Prefer FHIR-shaped events:

- MedicationAdministration / Order / Discontinuation
- LabObservation
- DiagnosisEvent
- ProcedureEvent

Each with `effectiveTime`, status, dose/route when present, and provenance. Grow **event types**, not binary predicates.

### 4. Cross-document entity resolution

Dedup Patient / Encounter / RxNorm concept across envelopes **before** claiming a living KG. Mention→Concept is a prerequisite.

### 5. FHIR resource ingestion (before Kafka)

Map FHIR `Bundle` / `DocumentReference` / `Composition` text (and later MedicationStatement, Observation) onto `EventEnvelope`. One adapter. No bus yet.

### 6. Review queue for `NEEDS_REVIEW`

Status exists; no API. Minimum: `outputs/kg/pending.jsonl` + a tiny accept/reject CLI that appends a `DecisionEvent(actor=human)`. Pending Cypher type `PENDING_*` already exists when `lpg.emit_pending: true`.

### 7. Official terminology editions

Catalog `version: catalog-ypcc-0.1` is a slice label. Stamp SNOMED edition/date, RxNorm monthly release, LOINC version on `TerminologyLink` and on `clin:terminologyVersion`.

### 8. LLM-adjudication evaluation (separate from NER F1)

Gold: schema-forbidden vs ambiguous vs valid-low-conf. Metrics: agreement with human, over-accept rate, CAUTION rate, cost/escalation. Do **not** fold this into NCBI Disease F1.

### 9. PHI stays experimental; stack Presidio later

Deterministic rules → Presidio / clinical PHI → GLiNER PII → span fusion → policy. Optimize **recall / false negatives**. Keep the README disclaimer.

### 10. Then a bus

Kafka / Pub/Sub / FHIR Subscription **after** envelope + FHIR adapter + idempotent upsert are boring. Consumer group, checkpoint, upsert/retract. Not before.

---

## Explicitly later (production bar)

BAA, DUA handling, audit log, KMS, ONNX/GPU SLOs, human review UI, full SNOMED RF2 / RxNorm, certified de-identification.

---

## If we only do four more things

1. SHACL from `ontology_rules.json` + pyshacl on the rdflib graph  
2. Mention vs Concept vs Assertion in the data model (even if resolution is still per-document)  
3. MedicationAdministration / LabObservation event types with `effectiveTime`  
4. FHIR Bundle → `EventEnvelope` + pending-review JSONL  

That is the path from “GLiNER → KG demo” to the control plane the review asked to preserve.
