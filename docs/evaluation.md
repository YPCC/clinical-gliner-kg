# Evaluation

Metrics the architecture spike is built to report:

| Metric | Meaning |
|---|---|
| Entity P / R / F1 | Span + type after hyphen/space normalization |
| Relation F1 | `(subject, relation, object)` triples |
| Ontology pass rate | Domain-range valid among predicted relations |
| Entity linked rate | Share of non-PHI entities with a terminology code |
| PHI recall | Gold identifiers recovered (substring match) |
| Over-redaction | Predicted PHI spans that match no gold identifier |
| p50 / p95 latency | Wall time per document |
| docs/s | Throughput |
| Planning USD / document | CPU-hour rate + fee only on escalated docs |

## Live GLiNER 2.5 spike (CPU)

Checkpoint: `fastino/gliner2.5-small-v1`. Zero-shot labels `disease` and `chemical`. 30 test documents per corpus.

| Corpus | Entity P / R / F1 | Rel F1 | Ont. pass | Linked | P95 | docs/s |
|---|---|---|---|---|---|---|
| NCBI Disease | 0.22 / 0.35 / 0.27 | n/a | 1.00 | 0.02 | 0.21 s | 6.1 |
| BC5CDR | 0.55 / 0.43 / 0.48 | 0.00 | 1.00 | 0.04 | 0.62 s | 2.4 |
| Synthetic PHI | — | — | — | — | — | recall 0.91, over-redaction 0.00 |

This is a 74M generalist encoder, not a BioBERT number. Linked rate is low because the default ontology is the bundled mini OBO. `sqlite:obo:mondo` is the next lever.

Reproduce:

```bash
pip install -e ".[all]"
python examples/run_literature_benchmark.py --backend gliner25 --limit 30
python examples/run_architecture_spike.py --backend heuristic
python examples/run_phi_benchmark.py
```

## Cost model (planning, not an invoice)

Assumptions: $0.40 / CPU-hour; $0.012 only if a document is escalated to an LLM. Local GLiNER has no token bill.

On the 30-doc NCBI slice, local compute was about **$1.81 / 100k**. The higher planning figure in the README includes the rare escalation fee.

![Cost planning infographic](images/cost-planning-matrix.jpg)
