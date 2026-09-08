# C4 Level 1 — System Context

People and external systems around Clinical-GLiNER-KG. The box in the middle is this repository.

```mermaid
C4Context
title Clinical-GLiNER-KG — System Context

Person(analyst, "Clinical informaticist / NLP engineer", "Runs the cascade on notes, literature, or FHIR text.")
Person(reviewer, "Clinician / HIM reviewer", "Inspects NEEDS_REVIEW assertions. Not in the runtime today.")

System(cgk, "Clinical-GLiNER-KG", "Reference extraction plane: GLiNER sensing → PHI gate → terminology + schema rules → optional LLM → Cypher/JSON-LD/Turtle.")

System_Ext(notes, "Clinical / literature text", "Synthetic notes in-repo; NCBI Disease, BC5CDR; DUA corpora stay off GitHub.")
System_Ext(gliner, "GLiNER 2.5", "Local AutoExtractor weights, or Pioneer / Hugging Face Inference APIs.")
System_Ext(oak, "oaklib + ontologies", "Local OBO/SQLite (default). Optional OLS or BioPortal.")
System_Ext(llm, "LLM providers", "OpenAI, Gemini API key, OpenAI-compatible base_url, or Vertex ADC.")
System_Ext(graph, "Graph / RDF store", "Neo4j, RDFLib file, or downstream KG. Not bundled.")
System_Ext(stream, "Event bus (planned)", "FHIR Subscription / Kafka / Pub/Sub. Not implemented.")

Rel(analyst, cgk, "Configures pipeline.yaml and runs process_document()")
Rel(cgk, notes, "Reads documents")
Rel(cgk, gliner, "Entity + relation candidates")
Rel(cgk, oak, "Grounds spans to CURIEs")
Rel(cgk, llm, "Adjudicates only ambiguous / low-confidence relations")
Rel(cgk, graph, "Emits Cypher, JSON-LD, Turtle")
Rel(reviewer, graph, "Reviews NEEDS_REVIEW assertions")
Rel_Dotted(stream, cgk, "Future event envelope")
```

## Boundary notes

- **PHI/PII** must not leave the box when `gliner.mode` and `oaklib.mode` are `local` and `llm.provider` is `none`.
- Hosted Pioneer, Hugging Face, OLS, BioPortal, and LLM APIs send spans off-box. That is a policy choice in `config/pipeline.yaml`, not a default.
- There is no Kafka/Pub/Sub consumer yet. The public API is `ClinicalSemanticExtractionPipeline.process_document(text, document_id)`.
