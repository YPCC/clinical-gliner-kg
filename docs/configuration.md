# How to use `config/pipeline.yaml`

One YAML file selects **local vs API** for GLiNER, oaklib, and the LLM.  
**API keys never go in YAML.** They live in the environment (or GCP ADC). The YAML only names which env var to read (`token_env`).

```
CLI flag  →  environment variable  →  YAML  →  library default
```

String values expand `$VAR` / `${VAR}`.

## 1. Choose a file

| File | Intent |
|---|---|
| [`config/pipeline.yaml`](../config/pipeline.yaml) | Default local / offline demo |
| [`config/pipeline.api-keys.example.yaml`](../config/pipeline.api-keys.example.yaml) | Hosted Pioneer + OpenAI + BioPortal |
| [`config/pipeline.google-api-key.example.yaml`](../config/pipeline.google-api-key.example.yaml) | Gemini via `GOOGLE_API_KEY` |
| [`config/pipeline.openai-compat.example.yaml`](../config/pipeline.openai-compat.example.yaml) | Any OpenAI-compatible `base_url` + key |

```bash
# inspect what the process will actually use (secret values are redacted)
clinical-gliner --config config/pipeline.yaml --print-config
```

## 2. Local (no keys) — default

This is already `config/pipeline.yaml`:

```yaml
backend: auto
gliner:
  mode: local                          # weights on this box
oaklib:
  mode: local                          # bundled mini OBO
llm:
  provider: none
  enable: false
```

```bash
python examples/run_pipeline.py --config config/pipeline.yaml --backend heuristic
```

oaklib still needs **ontology files on disk**, not an API. See [oaklib-grounding.md](oaklib-grounding.md).

## 3. API-key example (Pioneer + OpenAI + BioPortal)

Copy the example overlay, put keys in `.env`, then point `--config` at the copy.

### YAML (`config/pipeline.api-keys.example.yaml`)

```yaml
backend: gliner25

gliner:
  mode: pioneer                        # Fastino hosted GLiNER
  model: fastino/gliner2.5-small-v1
  pioneer:
    base_url: https://api.pioneer.ai
    token_env: PIONEER_API_KEY         # name of the env var, not the key

oaklib:
  mode: bioportal                      # NCBO annotator (sends spans off-box)
  bioportal:
    token_env: BIOPORTAL_API_KEY
    selectors:
      - "bioportal:"

llm:
  provider: openai
  enable: true                         # both enable and a key are required
  openai:
    model: gpt-4o-mini
    token_env: OPENAI_API_KEY
```

### `.env` (the actual keys)

```bash
cp config/pipeline.api-keys.example.yaml config/pipeline.local.yaml
cp .env.example .env
```

Edit `.env` (never commit it):

```bash
# GLiNER hosted — https://docs.pioneer.ai/authentication
PIONEER_API_KEY=pk_live_replace_me

# LLM exception path — https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-replace_me
LLM_ENABLE=1
LLM_PROVIDER=openai

# oaklib BioPortal — https://bioportal.bioontology.org/account
BIOPORTAL_API_KEY=replace_me

OAK_MODE=bioportal
GLINER_MODE=pioneer
CLINICAL_GLINER_BACKEND=gliner25
```

### Run

```bash
set -a && source .env && set +a

clinical-gliner --config config/pipeline.local.yaml --print-config
# secrets.PIONEER_API_KEY / OPENAI_API_KEY / BIOPORTAL_API_KEY should be true

python examples/run_pipeline.py \
  --config config/pipeline.local.yaml \
  --backend gliner25

clinical-gliner --config config/pipeline.local.yaml \
  "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."
```

If `--print-config` shows a secret as `false`, the process cannot see the env var (you forgot `source .env`, or the name does not match `token_env`).

### Hugging Face instead of Pioneer

Same pattern; only GLiNER changes:

```yaml
gliner:
  mode: huggingface_api
  model: fastino/gliner2.5-small-v1
  huggingface:
    endpoint: https://api-inference.huggingface.co/models
    token_env: HF_TOKEN
```

```bash
export GLINER_MODE=huggingface_api
export HF_TOKEN=hf_replace_me
```

Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). Not every GLiNER checkpoint exposes a working Inference API; Pioneer is the supported hosted path.

## 4. Google Gemini API key (not Vertex)

Google gives you two auth styles. This one is an **API key** against the Gemini OpenAI-compatible endpoint ([docs](https://ai.google.dev/gemini-api/docs/openai)). No GCP project, no ADC.

Copy [`config/pipeline.google-api-key.example.yaml`](../config/pipeline.google-api-key.example.yaml):

```yaml
llm:
  provider: google
  enable: true
  google:
    model: gemini-2.0-flash
    token_env: GOOGLE_API_KEY          # also accepts GEMINI_API_KEY
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
```

```bash
cp config/pipeline.google-api-key.example.yaml config/pipeline.local.yaml
export GOOGLE_API_KEY=AIza-replace_me    # https://aistudio.google.com/apikey
# or: export GEMINI_API_KEY=AIza-replace_me
export LLM_PROVIDER=google
export LLM_ENABLE=1

clinical-gliner --config config/pipeline.local.yaml --print-config
python examples/run_pipeline.py --config config/pipeline.local.yaml --backend heuristic
```

`--print-config` should show `secrets.GOOGLE_API_KEY: true`.

Vertex ADC (`llm.provider: vertex` + `gcloud auth application-default login`) is a different path — see section 6.

## 5. Any OpenAI-compatible API key

Anything that speaks `POST {base_url}/chat/completions` with `Authorization: Bearer`: Groq, Together, Fireworks, vLLM, Ollama, LiteLLM, Pioneer `/v1`, local OpenAI proxies.

Copy [`config/pipeline.openai-compat.example.yaml`](../config/pipeline.openai-compat.example.yaml):

```yaml
llm:
  provider: openai_compat
  enable: true
  openai_compat:
    model: llama-3.1-70b-versatile
    token_env: OPENAI_API_KEY          # whatever the vendor named the key
    base_url: https://api.groq.com/openai/v1
```

```bash
cp config/pipeline.openai-compat.example.yaml config/pipeline.local.yaml
export OPENAI_API_KEY=gsk_replace_me
export LLM_BASE_URL=https://api.groq.com/openai/v1   # overlays base_url
export LLM_PROVIDER=openai_compat
export LLM_ENABLE=1
clinical-gliner --config config/pipeline.local.yaml --print-config
```

| Vendor | `base_url` | Key env |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Gemini API (OpenAI compat) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GOOGLE_API_KEY` |
| Groq | `https://api.groq.com/openai/v1` | `OPENAI_API_KEY` |
| Together | `https://api.together.xyz/v1` | `OPENAI_API_KEY` |
| Ollama | `http://localhost:11434/v1` | any non-empty dummy key |
| vLLM | `http://localhost:8000/v1` | optional |
| LiteLLM proxy | your proxy `/v1` | proxy key |

You can also set `llm.openai.base_url` while keeping `provider: openai` if you only need a custom OpenAI proxy.

## 6. Vertex on GCP (ADC, no API key)

YAML selects Vertex; Google auth is Application Default Credentials, not an `API_KEY` env var.

```yaml
llm:
  provider: vertex
  enable: true
  vertex:
    model: gemini-2.0-flash
    location: us-central1
gcp:
  use_adc: true
  project: my-gcp-project
  credentials_file: ""                 # empty = ADC chain
```

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=my-gcp-project
export LLM_PROVIDER=vertex
export LLM_ENABLE=1
clinical-gliner --config config/pipeline.yaml --print-config
```

ADC search order: `gcp.credentials_file` → `GOOGLE_APPLICATION_CREDENTIALS` → `gcloud auth application-default login` → GCE/GKE/Cloud Run metadata. Docs: [ADC](https://cloud.google.com/docs/authentication/application-default-credentials) · [Vertex AI auth](https://cloud.google.com/vertex-ai/docs/authentication).

## 7. What each mode means

### GLiNER

| `gliner.mode` | What happens | Secret |
|---|---|---|
| `local` | `AutoExtractor.from_pretrained` on this box | optional `HF_TOKEN` for gated Hub repos |
| `huggingface_api` | POST Hugging Face Inference API | `HF_TOKEN` |
| `pioneer` | POST `https://api.pioneer.ai/inference` | `PIONEER_API_KEY` |

Env: `GLINER_MODE`, `GLINER25_MODEL`, `GLINER_SPACY_MODEL`, `GLINER_PII_MODEL`.

### oaklib

| `oaklib.mode` | Network | Key |
|---|---|---|
| `local` | no (unless `eager: true` and `sqlite:obo:`) | none — you need the OBO/SQLite **files** |
| `ols` | EBI OLS4 | none |
| `bioportal` | NCBO BioPortal | `BIOPORTAL_API_KEY` |

Env: `OAK_MODE`, `OAK_EAGER=1`, `OAK_ADAPTERS=simpleobo:/data/mondo.obo,sqlite:/data/chebi.db`.

Official OAK docs: [home](https://incatools.github.io/ontology-access-kit/) · [local files FAQ](https://incatools.github.io/ontology-access-kit/faq/general.html).

### LLM

`enable: true` **and** a reachable credential are both required. Otherwise the heuristic adjudicator stays in charge.

| `llm.provider` | Auth |
|---|---|
| `none` | — |
| `openai` | `OPENAI_API_KEY` (+ optional `openai.base_url`) |
| `openai_compat` | `token_env` + `openai_compat.base_url` (any Chat Completions server) |
| `azure_openai` | `AZURE_OPENAI_API_KEY` + endpoint / deployment |
| `google` | `GOOGLE_API_KEY` or `GEMINI_API_KEY` (Gemini API, not Vertex) |
| `vertex` | GCP ADC + `gcp.project` |
| `anthropic` | `ANTHROPIC_API_KEY` |

Env: `LLM_PROVIDER`, `LLM_ENABLE=1`, `OPENAI_MODEL`, `LLM_BASE_URL`, `GOOGLE_API_KEY`. Aliases: `gemini` → `google`, `openai-compatible` → `openai_compat`.

### PHI

```yaml
phi:
  action: tag                 # tag | mask | route
  enable_gliner_pii: false
```

`PHI_ACTION`. PII weights follow `gliner.mode`.

## 8. Pass `--config` from examples

```bash
python examples/run_pipeline.py --config config/pipeline.local.yaml --backend gliner25
python examples/run_kg_demo.py --config config/pipeline.local.yaml --outdir outputs/kg
python examples/run_architecture_spike.py --config config/pipeline.local.yaml
python examples/run_literature_benchmark.py --config config/pipeline.local.yaml --backend gliner25 --limit 30
```

## 9. Safety

- Clinical spans leave the box when `gliner.mode` is `pioneer` / `huggingface_api` or `oaklib.mode` is `ols` / `bioportal`.
- Keep PHI notes on `gliner.mode: local` and `oaklib.mode: local` unless you have a BAA with the vendor.
- `.gitignore` already ignores `.env` and `config/pipeline.local.yaml` if you add the latter — still do not paste keys into git.
