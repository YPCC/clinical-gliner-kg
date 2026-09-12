# CINEX report export

[CINEX](https://www.cinex-guideline.org/) is a **reporting guideline** for clinical information-extraction *studies* (29 items, five dimensions), not a graph serialisation. Reichenpfader et al., *J Am Med Inform Assoc* 2026; ocag136.

This repo can emit the digital-form JSON so a run is comparable to other IE papers.

| Dimension | IDs | What we auto-fill |
|---|---|---|
| Information model | IM1–IM5 | Labels, relations, terminologies, mention/concept/assertion |
| Architecture | A1–A5 | Cascade, backends, PHI gate, LLM router, local vs API |
| Data | D1–D9 | Synthetic + NCBI/BC5CDR, DUA policy, PHI/PII/BII |
| Annotation | AN1–AN5 | In-repo gold vs no human IAA |
| Outcome | O1–O5 | P/R/F1, leak rate, cost/latency, limitations |

Items we cannot honestly complete stay `partial` or `not_reported`. Completeness is counted in the JSON.

```bash
clinical-gliner --format cinex --backend heuristic
export CINEX=1
python examples/run_pii_leakage_benchmark.py --action mask --cinex
```

```yaml
report:
  cinex: true
  cinex_items: config/cinex_items.yaml
```

`--format cinex` does **not** replace `graph.target: lpg|rdfs|both`. CINEX is a study checklist; Cypher/SPARQL remain graph artifacts.
