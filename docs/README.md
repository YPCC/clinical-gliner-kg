# Documentation

What this repository is, how to drive it from **`config/pipeline.yaml`**, how **oaklib** runs **locally without an API key**, and the papers / software that inspired it.

| Page | What it covers |
|---|---|
| [Configuration](configuration.md) | YAML how-to; Pioneer/OpenAI/BioPortal keys; **Gemini API key**; **OpenAI-compatible** `base_url`; Vertex ADC |
| [Overview](overview.md) | Purpose, non-goals, who it is for |
| [Architecture](architecture.md) | Cascade stages, mermaid diagrams, provenance |
| [C4 diagrams](c4/README.md) | Context, container, and system (component) views |
| [Next steps](next-steps.md) | Review-driven backlog: P0 shipped, P1–P4 remaining |
| [oaklib grounding](oaklib-grounding.md) | Local OBO / SQLite vs remote OLS/BioPortal |
| [Evaluation](evaluation.md) | Metrics, live GLiNER 2.5 spike, cost model |
| [Data policy](data-policy.md) | Open corpora vs DUA (n2c2, MIMIC) |
| [Bibliography](bibliography.md) | Papers, software, ontologies, datasets |
| [Infographics](infographics.md) | Shareable cascade and cost visuals |
| [LinkedIn post](linkedin-post.md) | Draft + 2-minute edit workflow |

Code lives in [`src/clinical_gliner_kg/`](../src/clinical_gliner_kg/). Runnable demos are in [`examples/`](../examples/).
