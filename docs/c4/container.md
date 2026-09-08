# C4 Level 2 — Container

Deployable / process-level pieces inside Clinical-GLiNER-KG. Today this is **one Python process**. The containers below are logical, matching `src/clinical_gliner_kg/`.

```mermaid
C4Container
title Clinical-GLiNER-KG — Container view

Person(analyst, "NLP engineer")

System_Boundary(cgk, "Clinical-GLiNER-KG") {
  Container(cli, "CLI / examples", "Python", "clinical-gliner, examples/run_*.py")
  Container(pipe, "Extraction pipeline", "Python", "ClinicalSemanticExtractionPipeline.process_document")
  Container(cfg, "Config + secrets", "YAML + env", "pipeline.yaml; API keys never in YAML; GCP ADC optional")
  ContainerDb(mini, "Mini OBO + catalogs", "Files", "data/ontologies/mini_clinical.obo, terminology_catalog.json, ontology_rules.json")
  Container(emit, "Graph serializers", "Python", "Cypher, JSON-LD, Turtle; drops PHI and rejected relations")
}

System_Ext(weights, "GLiNER checkpoints / Pioneer / HF")
System_Ext(llm, "OpenAI / Gemini / OpenAI-compat / Vertex")
System_Ext(ols, "OLS / BioPortal (optional)")
System_Ext(store, "Neo4j or RDF store")

Rel(analyst, cli, "Runs")
Rel(cli, cfg, "load_settings()")
Rel(cli, pipe, "process_document")
Rel(pipe, mini, "Catalog + domain-range rules + oaklib simpleobo")
Rel(pipe, weights, "NER / RelEx / optional PII")
Rel(pipe, llm, "Only if llm.enable and a key/ADC is present")
Rel(pipe, ols, "If oaklib.mode is ols or bioportal")
Rel(pipe, emit, "ClinicalKnowledgeGraph")
Rel(emit, store, "Artifacts under outputs/")
```

## What is *not* a container yet

| Missing | Why it is listed in next-steps |
|---|---|
| Stream adapter | No Kafka / Pub/Sub / FHIR Subscription worker |
| Review UI | `NEEDS_REVIEW` is a status, not a queue |
| Terminology service | oaklib files, not a hosted CTS |
| Graph database | Serializers only; you load Cypher/Turtle yourself |
