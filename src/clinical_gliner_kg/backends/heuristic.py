"""Deterministic high-recall candidate generator used when model weights are unavailable.

This is not a production NER model. It keeps the cascade demo, tests, and CI runnable
without downloading GLiNER checkpoints, and it is a useful baseline for the architecture
spike (regex/lexicon recall vs. encoder vs. LLM).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation


@dataclass(frozen=True)
class Lexeme:
    pattern: str
    label: str
    confidence: float = 0.91


LEXICON: list[Lexeme] = [
    Lexeme(r"type 2 diabetes mellitus", "Condition", 0.97),
    Lexeme(r"type 2 diabetes", "Condition", 0.97),
    Lexeme(r"diabetes mellitus", "Condition", 0.93),
    Lexeme(r"essential hypertension", "Condition", 0.96),
    Lexeme(r"hypertension", "Condition", 0.94),
    Lexeme(r"heart failure", "Condition", 0.94),
    Lexeme(r"chronic kidney disease", "Condition", 0.95),
    Lexeme(r"community[- ]acquired pneumonia", "Condition", 0.95),
    Lexeme(r"pneumonia", "Condition", 0.90),
    Lexeme(r"atrial fibrillation", "Condition", 0.95),
    Lexeme(r"metformin", "Medication", 0.96),
    Lexeme(r"lisinopril", "Medication", 0.96),
    Lexeme(r"atorvastatin", "Medication", 0.96),
    Lexeme(r"furosemide", "Medication", 0.95),
    Lexeme(r"warfarin", "Medication", 0.95),
    Lexeme(r"ceftriaxone", "Medication", 0.95),
    Lexeme(r"hemoglobin a1c", "Laboratory_Test", 0.95),
    Lexeme(r"hba1c", "Laboratory_Test", 0.94),
    Lexeme(r"serum creatinine", "Laboratory_Test", 0.94),
    Lexeme(r"blood pressure", "Laboratory_Test", 0.88),
    Lexeme(r"\bbnp\b", "Laboratory_Test", 0.90),
    Lexeme(r"\binr\b", "Laboratory_Test", 0.90),
    Lexeme(r"chest x-ray", "Procedure", 0.90),
    Lexeme(r"echocardiogram", "Procedure", 0.92),
    Lexeme(r"left ventricle", "Anatomy", 0.90),
    Lexeme(r"\bkidney\b", "Anatomy", 0.86),
    Lexeme(r"\blungs?\b", "Anatomy", 0.84),
    Lexeme(r"\bpatient\b", "Patient", 0.80),
]

RESULT_RE = re.compile(
    r"(?P<val>\d+(?:\.\d+)?\s*(?:%|mg/dL|mmHg|pg/mL)?)",
    re.IGNORECASE,
)


class HeuristicBackend:
    name = "heuristic"

    def __init__(self, **_kwargs) -> None:
        return

    def extract(self, text: str) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
        entities: list[ClinicalEntity] = []
        occupied: list[tuple[int, int]] = []
        lower = text.lower()

        for idx, lex in enumerate(LEXICON):
            for match in re.finditer(lex.pattern, lower, flags=re.IGNORECASE):
                start, end = match.start(), match.end()
                if any(not (end <= a or start >= b) for a, b in occupied):
                    continue
                occupied.append((start, end))
                surface = text[start:end]
                entities.append(
                    ClinicalEntity(
                        id=f"ent_{lex.label.lower()}_{idx}_{start}",
                        text=surface,
                        label=lex.label,
                        start_char=start,
                        end_char=end,
                        confidence=lex.confidence,
                        source_model="heuristic-lexicon",
                    )
                )

        for match in RESULT_RE.finditer(text):
            start, end = match.start(), match.end()
            window = lower[max(0, start - 24) : min(len(lower), end + 8)]
            if not any(token in window for token in ("hba1c", "creatinine", "mmhg", "inr", "bnp", "%")):
                continue
            if any(not (end <= a or start >= b) for a, b in occupied):
                continue
            occupied.append((start, end))
            entities.append(
                ClinicalEntity(
                    id=f"ent_result_{start}",
                    text=match.group("val").strip(),
                    label="Laboratory_Result",
                    start_char=start,
                    end_char=end,
                    confidence=0.88,
                    source_model="heuristic-lexicon",
                )
            )

        relations = self._infer_relations(entities, lower)
        return entities, relations

    def _infer_relations(self, entities: list[ClinicalEntity], lower: str) -> list[ClinicalRelation]:
        by_label: dict[str, list[ClinicalEntity]] = {}
        for ent in entities:
            by_label.setdefault(ent.label, []).append(ent)

        relations: list[ClinicalRelation] = []

        def add(subj: ClinicalEntity, rel: str, obj: ClinicalEntity, conf: float) -> None:
            relations.append(
                ClinicalRelation(
                    subject_id=subj.id,
                    relation=rel,
                    object_id=obj.id,
                    confidence=conf,
                    source_model="heuristic-relex",
                )
            )

        patients = by_label.get("Patient", [])
        conditions = by_label.get("Condition", [])
        meds = by_label.get("Medication", [])
        tests = by_label.get("Laboratory_Test", [])
        results = by_label.get("Laboratory_Result", [])
        anatomy = by_label.get("Anatomy", [])

        for patient in patients:
            for cond in conditions:
                add(patient, "HAS_CONDITION", cond, 0.90)
            for med in meds:
                add(patient, "TAKES", med, 0.88)
        for med in meds:
            for cond in conditions:
                add(med, "TREATS", cond, 0.86)
            # Intentional negative candidate when the text mentions an anatomical site near a drug.
            if anatomy and "kidney" in lower and med.text.lower() == "metformin":
                add(med, "HAS_ANATOMICAL_SITE", anatomy[0], 0.42)
        for test in tests:
            for result in results:
                add(test, "HAS_VALUE", result, 0.90)
            for cond in conditions:
                if any(token in lower for token in ("because", "due to", "increased", "elevated")):
                    add(test, "INDICATES", cond, 0.72)
        return relations
