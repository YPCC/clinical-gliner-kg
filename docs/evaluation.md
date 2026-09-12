# Evaluation

Metrics the architecture spike is built to report:

| Metric | Meaning |
|---|---|
| Entity P / R / F1 | Span + type after hyphen/space normalization |
| Relation F1 | `(subject, relation, object)` triples |
| Ontology pass rate | Domain-range valid among predicted relations |
| Entity linked rate | Share of non-PHI entities with a terminology code |
| PHI/PII/BII precision, recall, F1 | Detector vs gold identifier spans |
| **Leak rate** | Gold identifiers still readable in the output (privacy-first; lower is better) |
| Over-redaction | Predicted PHI spans that match no gold identifier |
| DeepTeam pass rate | Case-level binary (1 = no leak) per [PIILeakage](https://trydeepteam.com/docs/red-teaming-vulnerabilities-pii-leakage) |
| p50 / p95 latency | Wall time per document |
| docs/s | Throughput |
| Planning USD / document | CPU-hour rate + fee only on escalated docs |

CINEX O1 is filled from these numbers: [cinex.md](cinex.md).

## PII / BII leakage (DeepTeam-aligned)

[DeepTeam `PIILeakage`](https://trydeepteam.com/docs/red-teaming-vulnerabilities-pii-leakage) evaluates whether an LLM *or* a pipeline output reveals sensitive personal information. Types:

| Type | What we test |
|---|---|
| `direct_disclosure` | Names, phones, emails, SSN, MRN in the note |
| `api_and_database_access` | SQL-like dumps of identifier columns |
| `session_leak` | Another patient's identifiers left in context |
| `social_manipulation` | A plea to "share the SSN" still containing real identifiers |

DeepTeam's `PIIMetric` is **binary** (0 leak / 1 pass). We keep that as `deepteam_pass_rate` and add span-level **precision, recall, F1, leak_rate**.

**Leak rate** = gold identifier spans whose surface form is still in the *masked* output (or that the detector missed, for `tag`). Lower is better. This is the privacy-first number; F1 can look fine while leak_rate is not.

**BII** (business identifiable information: account numbers, contract IDs, internal tickets) is a separate family. DeepTeam defines PII, not BII; splitting them stops a strong PII regex from hiding BII misses.

```bash
python examples/run_pii_leakage_benchmark.py --action mask
python examples/run_pii_leakage_benchmark.py --action mask --cinex
python examples/run_phi_benchmark.py --action mask
```

This gate is **experimental**, not a HIPAA de-identification program.

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
python examples/run_pii_leakage_benchmark.py --action mask
```

## Cost model (planning, not an invoice)

Assumptions: $0.40 / CPU-hour; $0.012 only if a document is escalated to an LLM. Local GLiNER has no token bill.

On the 30-doc NCBI slice, local compute was about **$1.81 / 100k**. The higher planning figure in the README includes the rare escalation fee.

![Cost planning infographic](images/cost-planning-matrix.jpg)
