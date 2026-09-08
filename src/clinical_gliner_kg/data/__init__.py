"""Load bundled synthetic notes and describe open / DUA catalog datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_synthetic_clinical_notes() -> list[dict[str, Any]]:
    return load_jsonl(repo_root() / "data" / "synthetic" / "clinical_notes.jsonl")


def load_synthetic_phi_notes() -> list[dict[str, Any]]:
    return load_jsonl(repo_root() / "data" / "synthetic" / "phi_notes.jsonl")


def load_gold_annotations() -> list[dict[str, Any]]:
    return load_jsonl(repo_root() / "data" / "synthetic" / "gold_annotations.jsonl")


def load_medical_data_catalog() -> dict[str, Any]:
    path = repo_root() / "data" / "catalogs" / "medical_data_index.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dataset_access_warning(entry: dict[str, Any]) -> str | None:
    access = str(entry.get("access", "")).lower()
    if access in {"dua", "restricted", "credentialed"}:
        return (
            f"{entry.get('name')} is {access}. Obtain it from {entry.get('url')} "
            "and do not commit source notes to git."
        )
    return None
