# Configuration

One file drives runtime choices: [`config/pipeline.yaml`](../config/pipeline.yaml).

**Secrets never go in YAML.** Keys live in the environment. Google auth uses [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).

```bash
python examples/run_pipeline.py --config config/pipeline.yaml --backend heuristic
clinical-gliner --config config/pipeline.yaml --print-config
```

Resolution for each field: **CLI flag → environment variable → YAML → library default.**

`$VAR` / `${VAR}` in string values are expanded.

## Modes at a glance

| Layer | Local (default) | Hosted / API |
|---|---|---|
| GLiNER | `gliner.mode: local` — weights on this box | `huggingface_api` (`HF_TOKEN`) or `pioneer` (`PIONEER_API_KEY`) |
| oaklib | `oaklib.mode: local` — OBO / SQLite files | `ols` (EBI OLS4) or `bioportal` (`BIOPORTAL_API_KEY`) |
| LLM | `llm.provider: none` | `openai` / `azure_openai` / `vertex` (ADC) / `anthropic` |
| GCP | ADC file on disk or metadata server | — |

## GLiNER

```yaml
gliner:
  mode: local                 # local | huggingface_api | pioneer
  model: fastino/gliner2.5-small-v1
```

| mode | What happens | Secret |
|---|---|---|
| `local` | `AutoExtractor.from_pretrained` (Hub download, CPU/GPU here) | optional `HF_TOKEN` for gated repos |
| `huggingface_api` | POST to Hugging Face Inference API | `HF_TOKEN` |
| `pioneer` | Fastino Pioneer `POST https://api.pioneer.ai/inference` | `PIONEER_API_KEY` |

Env aliases: `GLINER_MODE`, `GLINER25_MODEL`, `GLINER_SPACY_MODEL`, `GLINER_PII_MODEL`.

## oaklib (local files vs API)

Default is **offline**. You need ontology *files*, not an API key. See [oaklib-grounding.md](oaklib-grounding.md) and the [OAK docs](https://incatools.github.io/ontology-access-kit/).

```yaml
oaklib:
  mode: local                 # local | ols | bioportal
  eager: false
  local:
    adapters:
      - simpleobo:data/ontologies/mini_clinical.obo
      # - sqlite:/data/ontologies/mondo.db
```

| mode | Network | Key |
|---|---|---|
| `local` | no (unless a selector is `sqlite:obo:` and `eager: true`) | none |
| `ols` | yes (EBI OLS4) | none |
| `bioportal` | yes | `BIOPORTAL_API_KEY` |

`OAK_MODE`, `OAK_EAGER=1`, `OAK_ADAPTERS=simpleobo:/data/mondo.obo,sqlite:/data/chebi.db`.

## LLM

```yaml
llm:
  provider: none              # none | openai | azure_openai | vertex | anthropic
  enable: false
  openai:
    model: gpt-4o-mini
  vertex:
    model: gemini-2.0-flash
    location: us-central1
```

`enable: true` and a reachable credential are both required before spaCy-LLM / Vertex actually run. Otherwise the heuristic adjudicator stays in charge.

| provider | Auth |
|---|---|
| `none` | — |
| `openai` | `OPENAI_API_KEY` |
| `azure_openai` | `AZURE_OPENAI_API_KEY` + endpoint/deployment |
| `vertex` | **GCP ADC** (below) + `gcp.project` |
| `anthropic` | `ANTHROPIC_API_KEY` |

`LLM_PROVIDER`, `LLM_ENABLE=1`, `OPENAI_MODEL`.

## GCP Application Default Credentials

Used when `llm.provider: vertex` (and any later GCS sink).

```yaml
gcp:
  use_adc: true
  project: my-gcp-project          # or GOOGLE_CLOUD_PROJECT
  location: us-central1
  credentials_file: ""             # empty = ADC chain
  quota_project: ""
```

ADC search order (Google’s, not ours):

1. `credentials_file` in YAML, if set → exported as `GOOGLE_APPLICATION_CREDENTIALS`
2. `GOOGLE_APPLICATION_CREDENTIALS` already in the environment
3. User ADC from `gcloud auth application-default login`
4. GCE / GKE / Cloud Run metadata server

```bash
# Workstation
gcloud auth application-default login
gcloud config set project my-gcp-project

# Service account on a VM / in CI
export GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/sa.json
export GOOGLE_CLOUD_PROJECT=my-gcp-project
```

Docs: [ADC](https://cloud.google.com/docs/authentication/application-default-credentials) · [Vertex AI auth](https://cloud.google.com/vertex-ai/docs/authentication).

The pipeline calls `google.auth.default()` only when `llm.provider` is `vertex`; it does not invent a second credential mechanism.

## PHI

```yaml
phi:
  action: tag                 # tag | mask | route
  enable_gliner_pii: false
```

`PHI_ACTION`. PII weights follow `gliner.mode` (local vs Pioneer vs HF).

## Print the resolved config

```bash
clinical-gliner --print-config
```

Secret *values* are never printed; only whether the env var is set.
