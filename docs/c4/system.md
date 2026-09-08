# C4 Level 3 — System (extraction plane components)

Component view of the Python pipeline. This is the “system internals” diagram.

Statuses in **bold** are what the code writes today (`ValidationStatus`).

```mermaid
C4Component
title Clinical-GLiNER-KG — Extraction plane (components)

Container_Boundary(pipe, "Extraction pipeline") {
  Component(be, "Backends", "heuristic / gliner25 / gliner_spacy", "High-recall entity + relation candidates. RelEx binds arguments by span when offsets exist.")
  Component(phi, "PHI policy gate", "regex + optional GLiNER PII", "Offset mask, overlap dedupe. Not a HIPAA program.")
  Component(oak, "Grounder + catalog", "oaklib + JSON catalog", "LINKED or UNLINKED. Does not auto-VALIDATED.")
  Component(schema, "Schema validator", "ontology_rules.json", "Domain-range allow/deny. Not OWL/SHACL.")
  Component(router, "Confidence router", "Python", "valid+high → VALIDATED; forbidden → REJECTED; else escalate")
  Component(llm, "LLM adjudicator", "OpenAI-compat HTTP or Vertex ADC", "LLM_VALIDATED / LLM_REJECTED. If no LLM: NEEDS_REVIEW. Does not inflate confidence.")
  Component(emit, "Graph emitter", "Cypher / JSON-LD / Turtle", "Drops PHI nodes and relations whose endpoints were suppressed.")
}

Rel(be, phi, "entities, relations, spans")
Rel(phi, oak, "non-PHI spans")
Rel(oak, schema, "linked entities")
Rel(schema, router, "is_valid, comment")
Rel(router, llm, "ambiguous / low-confidence only")
Rel(router, emit, "VALIDATED / REJECTED")
Rel(llm, emit, "LLM_* or NEEDS_REVIEW")
```

## Implemented cascade (honest)

```mermaid
flowchart TD
  A[Clinical text] --> B[GLiNER or heuristic candidates]
  B --> C[PHI gate: regex → optional PII → tag/mask/route]
  C --> D[Catalog then oaklib annotate_text]
  D --> E{Entity terminology?}
  E -->|yes| L[LINKED]
  E -->|no| U[UNLINKED]
  L --> F[JSON domain-range rules]
  U --> F
  F --> G{Relation decision}
  G -->|allowed and confidence ≥ T| V[VALIDATED]
  G -->|explicit forbidden| R[REJECTED]
  G -->|ambiguous or low confidence| H{LLM configured and reachable?}
  H -->|yes| I[LLM_VALIDATED or LLM_REJECTED]
  H -->|no| N[NEEDS_REVIEW]
  V --> K[Emitter: skip PHI endpoints and REJECTED/LLM_REJECTED]
  I --> K
  N --> K
  R --> K
```

## Not in this diagram yet

- SHACL / OWL subclass inference (schema rules only)
- Assertion-level PROV graph with terminology version
- Stream envelope, idempotent upsert/retract
- Longitudinal entity resolution / coreference
