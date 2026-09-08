# Config files

| File | When to use |
|---|---|
| [`pipeline.yaml`](pipeline.yaml) | Default. Local GLiNER weights, local oaklib OBO, no LLM. |
| [`pipeline.api-keys.example.yaml`](pipeline.api-keys.example.yaml) | Hosted Pioneer + OpenAI + BioPortal. |
| [`pipeline.google-api-key.example.yaml`](pipeline.google-api-key.example.yaml) | Gemini via `GOOGLE_API_KEY` / `GEMINI_API_KEY`. |
| [`pipeline.openai-compat.example.yaml`](pipeline.openai-compat.example.yaml) | Any OpenAI-compatible `base_url` + API key. |
| [`ontology_rules.json`](ontology_rules.json) | Domain–range constraints |
| [`terminology_catalog.json`](terminology_catalog.json) | RxNorm / SNOMED / LOINC lookup table |
| [`spacy_llm.cfg`](spacy_llm.cfg) | spaCy-LLM NER.v3 task (OpenAI path) |

`graph.target` in `pipeline.yaml` selects **LPG/Cypher**, **RDFS/SPARQL**, or **both**. See [docs/graph.md](../docs/graph.md).
