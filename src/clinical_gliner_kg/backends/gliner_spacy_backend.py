"""Classic GLiNER via the official spaCy factory `gliner_spacy`.

The community wrapper (https://github.com/theirstory/gliner-spacy) loads
`urchade/GLiNER` checkpoints and writes `doc.ents` plus `span._.score`.
GLiNER 2.5 joint IE is handled by `backends/gliner25.py`; this backend is the
spaCy-native path requested for the showcase.
"""

from __future__ import annotations

import os

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation


CLINICAL_LABELS = [
    "Patient",
    "Condition",
    "Medication",
    "Laboratory_Test",
    "Laboratory_Result",
    "Anatomy",
    "Procedure",
    "Provider",
]


class GlinerSpacyBackend:
    name = "gliner_spacy"

    def __init__(self, model_name: str | None = None, threshold: float = 0.3) -> None:
        self.model_name = model_name or os.getenv("GLINER_SPACY_MODEL", "urchade/gliner_medium-v2.1")
        self.threshold = threshold
        try:
            import spacy
            import gliner_spacy  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "gliner-spacy / spaCy are not installed. "
                "Run `pip install 'clinical-gliner-kg[gliner]'`."
            ) from exc

        self.nlp = spacy.blank("en")
        self.nlp.add_pipe(
            "gliner_spacy",
            config={
                "gliner_model": self.model_name,
                "chunk_size": 250,
                "labels": CLINICAL_LABELS,
                "style": "ent",
                "threshold": threshold,
                "map_location": "cpu",
            },
        )

    def extract(self, text: str) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
        doc = self.nlp(text)
        entities: list[ClinicalEntity] = []
        for i, ent in enumerate(doc.ents):
            score = float(getattr(ent._, "score", 0.80) or 0.80)
            entities.append(
                ClinicalEntity(
                    id=f"ent_{i}",
                    text=ent.text,
                    label=ent.label_,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    confidence=score,
                    source_model=self.model_name,
                )
            )
        return entities, []
