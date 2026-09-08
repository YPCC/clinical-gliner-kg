from pathlib import Path

from clinical_gliner_kg.settings import apply_gcp_adc, load_settings
from clinical_gliner_kg.backends.hosted import _parse_hosted


def test_default_yaml_is_local_offline():
    settings = load_settings()
    assert settings.gliner.mode == "local"
    assert settings.oaklib.mode == "local"
    assert settings.llm.provider == "none"
    assert settings.gcp.use_adc is True
    selectors = settings.oak_selectors()
    assert any("mini_clinical.obo" in item for item in selectors)
    assert not any(item.startswith("ols") or item.startswith("bioportal") for item in selectors)


def test_env_overrides_modes(monkeypatch):
    monkeypatch.setenv("GLINER_MODE", "pioneer")
    monkeypatch.setenv("OAK_MODE", "ols")
    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-proj")
    settings = load_settings()
    assert settings.gliner.mode == "pioneer"
    assert settings.oaklib.mode == "ols"
    assert settings.llm.provider == "vertex"
    assert settings.gcp.project == "demo-proj"
    assert settings.oak_selectors() == ["ols4:mondo", "ols4:chebi"]


def test_gcp_adc_exports_credentials_file(monkeypatch, tmp_path):
    creds = tmp_path / "sa.json"
    creds.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    settings = load_settings()
    settings.gcp.credentials_file = str(creds)
    settings.gcp.project = "adc-test"
    apply_gcp_adc(settings.gcp)
    assert Path(os_env_must("GOOGLE_APPLICATION_CREDENTIALS")) == creds
    assert os_env_must("GOOGLE_CLOUD_PROJECT") == "adc-test"


def os_env_must(name: str) -> str:
    import os

    value = os.environ.get(name)
    assert value
    return value


def test_print_config_redacts_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    data = load_settings().redacted()
    assert data["secrets"]["OPENAI_API_KEY"] is True
    blob = str(data)
    assert "sk-test" not in blob


def test_hosted_parser_maps_hf_token_classification():
    raw = [
        {"word": "metformin", "entity_group": "medication", "start": 10, "end": 19, "score": 0.9},
        {"word": "x", "entity_group": "medication", "start": 0, "end": 1, "score": 0.01},
    ]
    ents, rels = _parse_hosted(raw, "started metformin", "demo", 0.3)
    assert len(ents) == 1
    assert ents[0].text == "metformin"
    assert rels == []


def test_pipeline_accepts_config_path():
    from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline

    pipeline = ClinicalSemanticExtractionPipeline(
        backend="heuristic",
        config_path=Path(__file__).resolve().parents[1] / "config" / "pipeline.yaml",
    )
    assert pipeline.settings.gliner.model.startswith("fastino/")
    kg = pipeline.process_document(
        "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%.",
        document_id="cfg",
    )
    assert kg.entities
