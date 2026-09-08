"""Extraction backend protocol and factory."""

from __future__ import annotations

from typing import Protocol

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation


class ExtractionBackend(Protocol):
    name: str

    def extract(self, text: str) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
        ...


def available_backends() -> list[str]:
    names = ["heuristic"]
    try:
        import gliner2  # noqa: F401

        names.append("gliner25")
    except Exception:
        pass
    try:
        import gliner_spacy  # noqa: F401
        import spacy  # noqa: F401

        names.append("gliner_spacy")
    except Exception:
        pass
    return names


def resolve_backend(name: str, **kwargs) -> ExtractionBackend:
    requested = (name or "auto").lower()
    if requested == "heuristic":
        from clinical_gliner_kg.backends.heuristic import HeuristicBackend

        return HeuristicBackend()
    if requested == "gliner25":
        from clinical_gliner_kg.backends.gliner25 import GLiNER25Backend

        return GLiNER25Backend(**kwargs)
    if requested in {"gliner_spacy", "gliner-spacy"}:
        from clinical_gliner_kg.backends.gliner_spacy_backend import GlinerSpacyBackend

        return GlinerSpacyBackend(**kwargs)
    if requested == "auto":
        try:
            from clinical_gliner_kg.backends.gliner25 import GLiNER25Backend

            return GLiNER25Backend(**kwargs)
        except Exception:
            try:
                from clinical_gliner_kg.backends.gliner_spacy_backend import GlinerSpacyBackend

                return GlinerSpacyBackend(**kwargs)
            except Exception:
                from clinical_gliner_kg.backends.heuristic import HeuristicBackend

                return HeuristicBackend()
    raise ValueError(f"Unknown backend '{name}'. Use auto | gliner25 | gliner_spacy | heuristic.")
