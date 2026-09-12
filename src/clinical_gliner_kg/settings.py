"""Load `config/pipeline.yaml` and overlay environment variables.

Secrets stay in the environment (or ADC). The YAML file chooses *modes*
(local vs API) and non-secret defaults.

Resolution order for a field: constructor override → environment → YAML → default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "pipeline.yaml"

GlinerMode = Literal["local", "huggingface_api", "pioneer"]
OakMode = Literal["local", "ols", "bioportal"]
LLMProvider = Literal[
    "none",
    "openai",
    "openai_compat",
    "azure_openai",
    "google",
    "vertex",
    "anthropic",
]
GraphTarget = Literal["lpg", "rdfs", "both"]
BackendName = Literal["auto", "gliner25", "gliner_spacy", "heuristic"]


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value).strip()
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item) for item in value]
    return value


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class GlinerHuggingFaceSettings(BaseModel):
    """Hugging Face Inference API (token in HF_TOKEN / HUGGING_FACE_HUB_TOKEN)."""

    endpoint: str = "https://api-inference.huggingface.co/models"
    token_env: str = "HF_TOKEN"


class GlinerPioneerSettings(BaseModel):
    """Fastino Pioneer hosted GLiNER (`PIONEER_API_KEY`)."""

    base_url: str = "https://api.pioneer.ai"
    token_env: str = "PIONEER_API_KEY"


class GlinerSpacySettings(BaseModel):
    model: str = "urchade/gliner_medium-v2.1"


class GlinerSettings(BaseModel):
    mode: GlinerMode = "local"
    model: str = "fastino/gliner2.5-small-v1"
    device: str = "cpu"
    threshold: float = 0.3
    enable_relations: bool = True
    enable_joint: bool = False
    huggingface: GlinerHuggingFaceSettings = Field(default_factory=GlinerHuggingFaceSettings)
    pioneer: GlinerPioneerSettings = Field(default_factory=GlinerPioneerSettings)
    spacy: GlinerSpacySettings = Field(default_factory=GlinerSpacySettings)
    pii_model: str = "fastino/gliner2-privacy-filter-PII-multi"


class OakLocalSettings(BaseModel):
    adapters: list[str] = Field(
        default_factory=lambda: ["simpleobo:data/ontologies/mini_clinical.obo"]
    )


class OakRemoteSettings(BaseModel):
    selectors: list[str] = Field(default_factory=list)
    token_env: str = ""


class OaklibSettings(BaseModel):
    mode: OakMode = "local"
    eager: bool = False
    local: OakLocalSettings = Field(default_factory=OakLocalSettings)
    ols: OakRemoteSettings = Field(
        default_factory=lambda: OakRemoteSettings(selectors=["ols4:mondo", "ols4:chebi"])
    )
    bioportal: OakRemoteSettings = Field(
        default_factory=lambda: OakRemoteSettings(
            selectors=["bioportal:"],
            token_env="BIOPORTAL_API_KEY",
        )
    )


class OpenAISettings(BaseModel):
    model: str = "gpt-4o-mini"
    token_env: str = "OPENAI_API_KEY"
    temperature: float = 0.0
    base_url: str = "https://api.openai.com/v1"


class AzureOpenAISettings(BaseModel):
    endpoint: str = ""
    deployment: str = ""
    api_version: str = "2024-10-21"
    token_env: str = "AZURE_OPENAI_API_KEY"


class GoogleAPISettings(BaseModel):
    """Gemini via API key (not Vertex ADC).

    Uses Google's OpenAI-compatible endpoint:
    https://generativelanguage.googleapis.com/v1beta/openai/
    Key: GOOGLE_API_KEY or GEMINI_API_KEY.
    """

    model: str = "gemini-2.0-flash"
    token_env: str = "GOOGLE_API_KEY"
    temperature: float = 0.0
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"


class VertexSettings(BaseModel):
    model: str = "gemini-2.0-flash"
    location: str = "us-central1"
    temperature: float = 0.0


class OpenAICompatSettings(BaseModel):
    """Any OpenAI Chat Completions compatible server.

    Examples: Groq, Together, Fireworks, vLLM, Ollama, LiteLLM, Pioneer /v1.
    """

    model: str = "gpt-4o-mini"
    token_env: str = "OPENAI_API_KEY"
    temperature: float = 0.0
    base_url: str = "https://api.openai.com/v1"


class AnthropicSettings(BaseModel):
    model: str = "claude-3-5-sonnet-latest"
    token_env: str = "ANTHROPIC_API_KEY"


class LLMSettings(BaseModel):
    provider: LLMProvider = "none"
    enable: bool = False
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    openai_compat: OpenAICompatSettings = Field(default_factory=OpenAICompatSettings)
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    google: GoogleAPISettings = Field(default_factory=GoogleAPISettings)
    vertex: VertexSettings = Field(default_factory=VertexSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)

    @field_validator("provider", mode="before")
    @classmethod
    def _alias_provider(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        aliases = {
            "gemini": "google",
            "google_api": "google",
            "openai-compatible": "openai_compat",
            "openai_compatible": "openai_compat",
            "compatible": "openai_compat",
        }
        return aliases.get(value.lower(), value.lower())


class GCPSettings(BaseModel):
    """Application Default Credentials for Vertex / GCS / other Google APIs.

    Empty `credentials_file` means the standard ADC chain:
    GOOGLE_APPLICATION_CREDENTIALS → `gcloud auth application-default login`
    → GCE/GKE/Cloud Run metadata server.
    """

    use_adc: bool = True
    project: str = ""
    location: str = "us-central1"
    credentials_file: str = ""
    quota_project: str = ""


class ReportSettings(BaseModel):
    """Study-level exports. cinex = CINEX 29-item JSON (not a graph dialect)."""

    cinex: bool = False
    cinex_items: str = "config/cinex_items.yaml"


class PHISettings(BaseModel):
    action: str = "tag"
    enable_gliner_pii: bool = False


class LpgSettings(BaseModel):
    dialect: str = "cypher"
    emit_pending: bool = True


class RdfsSettings(BaseModel):
    ontology: str = "data/ontologies/clinical.rdfs.ttl"
    serialization: str = "turtle"  # turtle | ntriples | jsonld | rdfxml
    infer: str = "none"  # none | rdfs
    base_iri: str = "https://ypcc.dev/clinical-gliner-kg/"
    include_assertions: bool = True


class GraphSettings(BaseModel):
    """LPG/Cypher, RDFS/SPARQL, or both."""

    target: GraphTarget = "both"
    lpg: LpgSettings = Field(default_factory=LpgSettings)
    rdfs: RdfsSettings = Field(default_factory=RdfsSettings)
    store_path: str = "outputs/kg/assertions.jsonl"

    @field_validator("target", mode="before")
    @classmethod
    def _alias_target(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        aliases = {
            "cypher": "lpg",
            "neo4j": "lpg",
            "rdf": "rdfs",
            "sparql": "rdfs",
            "jsonld": "rdfs",
            "all": "both",
        }
        return aliases.get(value.lower(), value.lower())

    def emit_lpg(self) -> bool:
        return self.target in {"lpg", "both"}

    def emit_rdfs(self) -> bool:
        return self.target in {"rdfs", "both"}


class PipelineSettings(BaseModel):
    pipeline_version: str = "0.1.0-cascaded"
    backend: BackendName = "auto"
    confidence_threshold: float = 0.75
    clinical_labels: list[str] = Field(
        default_factory=lambda: [
            "Patient",
            "Condition",
            "Medication",
            "Laboratory_Test",
            "Laboratory_Result",
            "Anatomy",
            "Procedure",
            "Provider",
        ]
    )
    relation_types: list[str] = Field(
        default_factory=lambda: [
            "HAS_CONDITION",
            "TAKES",
            "TREATS",
            "HAS_VALUE",
            "INDICATES",
            "PERFORMED",
            "HAS_ANATOMICAL_SITE",
        ]
    )
    gliner: GlinerSettings = Field(default_factory=GlinerSettings)
    oaklib: OaklibSettings = Field(default_factory=OaklibSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    gcp: GCPSettings = Field(default_factory=GCPSettings)
    phi: PHISettings = Field(default_factory=PHISettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)

    def oak_selectors(self) -> list[str]:
        if self.oaklib.mode == "ols":
            return list(self.oaklib.ols.selectors)
        if self.oaklib.mode == "bioportal":
            return list(self.oaklib.bioportal.selectors)
        return [_resolve_selector(item) for item in self.oaklib.local.adapters]

    def secret_present(self, env_name: str) -> bool:
        return bool(_env(env_name))

    def redacted(self) -> dict[str, Any]:
        """JSON-serialisable view with secret *names* only, never values."""
        data = self.model_dump()
        data["secrets"] = {
            "OPENAI_API_KEY": self.secret_present("OPENAI_API_KEY"),
            "PIONEER_API_KEY": self.secret_present("PIONEER_API_KEY"),
            "HF_TOKEN": self.secret_present("HF_TOKEN") or self.secret_present("HUGGING_FACE_HUB_TOKEN"),
            "BIOPORTAL_API_KEY": self.secret_present("BIOPORTAL_API_KEY"),
            "ANTHROPIC_API_KEY": self.secret_present("ANTHROPIC_API_KEY"),
            "AZURE_OPENAI_API_KEY": self.secret_present("AZURE_OPENAI_API_KEY"),
            "GOOGLE_API_KEY": self.secret_present("GOOGLE_API_KEY") or self.secret_present("GEMINI_API_KEY"),
            "GOOGLE_APPLICATION_CREDENTIALS": bool(self.gcp.credentials_file or _env("GOOGLE_APPLICATION_CREDENTIALS")),
            self.llm.openai_compat.token_env: self.secret_present(self.llm.openai_compat.token_env),
        }
        return data


def _resolve_selector(selector: str) -> str:
    selector = os.path.expandvars(selector)
    if selector.startswith("simpleobo:") and not selector.startswith("simpleobo:/") and "://" not in selector:
        rest = selector.split(":", 1)[1]
        path = Path(rest)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return f"simpleobo:{path}"
    if selector.startswith("sqlite:") and not selector.startswith("sqlite:obo:"):
        rest = selector.split(":", 1)[1]
        path = Path(rest)
        if not path.is_absolute() and not rest.startswith("obo:"):
            path = REPO_ROOT / path
            return f"sqlite:{path}"
    return selector


def apply_gcp_adc(gcp: GCPSettings) -> None:
    """Export ADC-related env vars so Google client libraries pick them up."""
    if not gcp.use_adc:
        return
    creds = gcp.credentials_file or _env("GOOGLE_APPLICATION_CREDENTIALS", "") or ""
    if creds:
        path = Path(os.path.expandvars(creds)).expanduser()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    if gcp.project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = gcp.project
        os.environ.setdefault("GCLOUD_PROJECT", gcp.project)
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", gcp.project)
    if gcp.quota_project:
        os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = gcp.quota_project
    if gcp.location:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", gcp.location)
        os.environ.setdefault("VERTEXAI_LOCATION", gcp.location)


def _overlay_env(raw: dict[str, Any]) -> dict[str, Any]:
    gliner = raw.setdefault("gliner", {})
    oak = raw.setdefault("oaklib", {})
    llm = raw.setdefault("llm", {})
    gcp = raw.setdefault("gcp", {})
    phi = raw.setdefault("phi", {})
    graph = raw.setdefault("graph", {})
    report = raw.setdefault("report", {})

    if backend := _env("CLINICAL_GLINER_BACKEND"):
        raw["backend"] = backend
    if model := _env("GLINER25_MODEL"):
        gliner["model"] = model
    if mode := _env("GLINER_MODE"):
        gliner["mode"] = mode
    if spacy_model := _env("GLINER_SPACY_MODEL"):
        gliner.setdefault("spacy", {})["model"] = spacy_model
    if pii := _env("GLINER_PII_MODEL"):
        gliner["pii_model"] = pii
    if _env("OAK_MODE"):
        oak["mode"] = _env("OAK_MODE")
    if os.getenv("OAK_EAGER") is not None:
        oak["eager"] = _env_bool("OAK_EAGER", False)
    extra = _env("OAK_ADAPTERS")
    if extra:
        oak.setdefault("local", {})["adapters"] = [item.strip() for item in extra.split(",") if item.strip()]
    if provider := _env("LLM_PROVIDER"):
        aliases = {"gemini": "google", "openai-compatible": "openai_compat", "openai_compatible": "openai_compat"}
        llm["provider"] = aliases.get(provider, provider)
    if os.getenv("LLM_ENABLE") is not None:
        llm["enable"] = _env_bool("LLM_ENABLE", False)
    if _env("OPENAI_MODEL"):
        llm.setdefault("openai", {})["model"] = _env("OPENAI_MODEL")
    if _env("LLM_BASE_URL"):
        llm.setdefault("openai_compat", {})["base_url"] = _env("LLM_BASE_URL")
        llm.setdefault("openai", {})["base_url"] = _env("LLM_BASE_URL")
    if _env("GOOGLE_API_MODEL"):
        llm.setdefault("google", {})["model"] = _env("GOOGLE_API_MODEL")
    if _env("GOOGLE_CLOUD_PROJECT"):
        gcp["project"] = _env("GOOGLE_CLOUD_PROJECT")
    if _env("GOOGLE_APPLICATION_CREDENTIALS"):
        gcp["credentials_file"] = _env("GOOGLE_APPLICATION_CREDENTIALS")
    if _env("GOOGLE_CLOUD_LOCATION"):
        gcp["location"] = _env("GOOGLE_CLOUD_LOCATION")
        llm.setdefault("vertex", {})["location"] = _env("GOOGLE_CLOUD_LOCATION")
    if action := _env("PHI_ACTION"):
        phi["action"] = action
    if target := _env("GRAPH_TARGET"):
        graph["target"] = target
    if store := _env("GRAPH_STORE"):
        graph["store_path"] = store
    if os.getenv("CINEX") is not None:
        report["cinex"] = _env_bool("CINEX", False)
    return raw


def _coerce_legacy(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept the original flat pipeline.yaml keys."""
    gliner = raw.setdefault("gliner", {})
    phi = raw.setdefault("phi", {})
    if "gliner25_model" in raw:
        gliner.setdefault("model", raw.pop("gliner25_model"))
    if "gliner_spacy_model" in raw:
        gliner.setdefault("spacy", {})["model"] = raw.pop("gliner_spacy_model")
    if "pii_model" in raw:
        gliner.setdefault("pii_model", raw.pop("pii_model"))
    if "phi_action" in raw:
        phi.setdefault("action", raw.pop("phi_action"))
    return raw


def load_settings(path: Path | str | None = None) -> PipelineSettings:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config {cfg_path} must be a mapping")
        raw = _expand(loaded)
    raw = _coerce_legacy(raw)
    raw = _overlay_env(raw)
    settings = PipelineSettings.model_validate(raw)
    apply_gcp_adc(settings.gcp)
    return settings
