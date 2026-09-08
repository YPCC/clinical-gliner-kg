# Config files

| File | When to use |
|---|---|
| [`pipeline.yaml`](pipeline.yaml) | Default. Local GLiNER weights, local oaklib OBO, no LLM. |
| [`pipeline.api-keys.example.yaml`](pipeline.api-keys.example.yaml) | Hosted APIs. Copy it, keep keys in `.env`. |
| [`ontology_rules.json`](ontology_rules.json) | Domain–range constraints |
| [`terminology_catalog.json`](terminology_catalog.json) | RxNorm / SNOMED / LOINC lookup table |
| [`spacy_llm.cfg`](spacy_llm.cfg) | spaCy-LLM NER.v3 task (OpenAI path) |

How to run them: [docs/configuration.md](../docs/configuration.md).
