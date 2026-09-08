"""oaklib-backed entity grounding (MONDO, ChEBI, HP, plus optional OLS/BioPortal).

Uses the Ontology Access Kit text-annotator and basic-search interfaces:

    from oaklib import get_adapter
    adapter = get_adapter("sqlite:obo:mondo")
    for ann in adapter.annotate_text("type 2 diabetes mellitus"):
        ...

Adapters are tried in order. If none can be opened (no download, no network
cache), the catalog linker still works as a deterministic fallback.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache

from pathlib import Path

from clinical_gliner_kg.models import ClinicalEntity, TerminologyLink


def _bundled_obo() -> str:
    path = Path(__file__).resolve().parents[3] / "data" / "ontologies" / "mini_clinical.obo"
    return f"simpleobo:{path}"


DEFAULT_ADAPTERS = {
    "Condition": [_bundled_obo()],
    "Disease": [_bundled_obo()],
    "Medication": [_bundled_obo()],
    "Chemical": [_bundled_obo()],
    "Anatomy": [_bundled_obo()],
    "Procedure": [_bundled_obo()],
    "Laboratory_Test": [_bundled_obo()],
}

CURIE_SYSTEM = {
    "MONDO": "MONDO",
    "CHEBI": "ChEBI",
    "HP": "HPO",
    "UBERON": "UBERON",
    "MESH": "MeSH",
    "OMIM": "OMIM",
    "DOID": "DOID",
    "RXNORM": "RxNorm",
    "SNOMEDCT": "SNOMED-CT",
    "SNOMED": "SNOMED-CT",
}


def _parse_curie(curie: str) -> tuple[str, str]:
    if ":" not in curie:
        return "UNKNOWN", curie
    prefix, code = curie.split(":", 1)
    system = CURIE_SYSTEM.get(prefix.upper(), prefix.upper())
    return system, code


class OaklibGrounder:
    """Ground entity spans with oaklib adapters; degrade gracefully if unavailable."""

    def __init__(
        self,
        adapters_by_label: dict[str, list[str]] | None = None,
        *,
        mode: str | None = None,
        eager: bool | None = None,
        selectors: list[str] | None = None,
        bioportal_token_env: str = "BIOPORTAL_API_KEY",
    ) -> None:
        extra = os.getenv("OAK_ADAPTERS", "").strip()
        self.mode = (mode or os.getenv("OAK_MODE") or "local").lower()
        if selectors:
            shared = selectors
            self.requested = {label: shared for label in DEFAULT_ADAPTERS}
        elif extra:
            shared = [item.strip() for item in extra.split(",") if item.strip()]
            self.requested = {label: shared for label in DEFAULT_ADAPTERS}
        else:
            self.requested = adapters_by_label or DEFAULT_ADAPTERS
        self._adapters: dict[str, list] = {}
        self.available: list[str] = []
        self._eager = bool(eager) if eager is not None else os.getenv("OAK_EAGER", "0") == "1"
        if self.mode == "bioportal" and not os.getenv(bioportal_token_env):
            # Adapter would fail anyway; skip load so CI stays quiet.
            return
        if self._eager or self.mode in {"ols", "bioportal"}:
            self._load()
        else:
            self._load_lightweight()

    def _load_lightweight(self) -> None:
        light = []
        for selectors in self.requested.values():
            for selector in selectors:
                if selector.startswith("sqlite:obo:") or selector.startswith("gilda:"):
                    continue
                light.append(selector)
        if not light:
            return
        try:
            from oaklib import get_adapter
        except ImportError:
            return
        seen = set()
        for selector in light:
            if selector in seen:
                continue
            seen.add(selector)
            try:
                adapter = get_adapter(selector)
                self._adapters[selector] = [adapter]
                self.available.append(selector)
            except Exception:
                continue

    def _load(self) -> None:
        try:
            from oaklib import get_adapter
        except ImportError:
            return
        seen: set[str] = set()
        for selectors in self.requested.values():
            for selector in selectors:
                if selector in seen:
                    continue
                seen.add(selector)
                try:
                    adapter = get_adapter(selector)
                    self._adapters.setdefault(selector, [])
                    self._adapters[selector] = [adapter]
                    self.available.append(selector)
                except Exception:
                    continue

    def enabled(self) -> bool:
        return bool(self.available)

    def ground(self, entity: ClinicalEntity) -> ClinicalEntity:
        if entity.terminology is not None:
            return entity
        text = entity.text.strip()
        if len(text) < 3:
            return entity
        selectors = self.requested.get(entity.label, ["sqlite:obo:mondo"])
        for selector in selectors:
            for adapter in self._adapters.get(selector, []):
                link = _annotate_one(adapter, text)
                if link:
                    entity.terminology = link
                    return entity
        return entity


@lru_cache(maxsize=4096)
def _annotate_cached(adapter_id: int, text: str) -> TerminologyLink | None:
    return None


def _annotate_one(adapter, text: str) -> TerminologyLink | None:
    cleaned = re.sub(r"\s+", " ", text).strip()
    try:
        anns = list(adapter.annotate_text(cleaned))
    except Exception:
        anns = []
    if not anns:
        try:
            hits = list(adapter.basic_search(cleaned))
        except Exception:
            hits = []
        if hits:
            curie = str(hits[0])
            system, code = _parse_curie(curie)
            label = _safe_label(adapter, curie) or cleaned
            return TerminologyLink(system=system, code=code, display=label, match_score=0.70, method="oaklib-search")
        return None

    best = anns[0]
    object_id = getattr(best, "object_id", None) or getattr(best, "objectId", None)
    object_label = getattr(best, "object_label", None) or getattr(best, "objectLabel", None) or cleaned
    if not object_id:
        return None
    system, code = _parse_curie(str(object_id))
    score = float(getattr(best, "confidence", 0.85) or 0.85)
    return TerminologyLink(
        system=system,
        code=code,
        display=str(object_label),
        match_score=score,
        method="oaklib-annotate",
    )


def _safe_label(adapter, curie: str) -> str | None:
    try:
        label = adapter.label(curie)
        return str(label) if label else None
    except Exception:
        return None
