"""GLiNER 2.5 backend via the official gliner2 AutoExtractor / JointIE APIs.

References
----------
- https://github.com/fastino-ai/GLiNER2
- https://huggingface.co/spaces/fastino/gliner25-long-context
"""

from __future__ import annotations

import os
from typing import Any

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation

DEFAULT_ENTITY_LABELS = [
    "patient",
    "condition",
    "medication",
    "laboratory_test",
    "laboratory_result",
    "anatomy",
    "procedure",
    "provider",
]

DEFAULT_RELATIONS = [
    "HAS_CONDITION",
    "TAKES",
    "TREATS",
    "HAS_VALUE",
    "INDICATES",
    "HAS_ANATOMICAL_SITE",
]

LABEL_MAP = {
    "patient": "Patient",
    "condition": "Condition",
    "chemical": "Chemical",
    "disease": "Disease",
    "diagnosis": "Condition",
    "medication": "Medication",
    "drug": "Medication",
    "laboratory_test": "Laboratory_Test",
    "lab_test": "Laboratory_Test",
    "test": "Laboratory_Test",
    "laboratory_result": "Laboratory_Result",
    "lab_result": "Laboratory_Result",
    "anatomy": "Anatomy",
    "procedure": "Procedure",
    "provider": "Provider",
}


def _normalize_label(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "_")
    return LABEL_MAP.get(key, raw.replace(" ", "_").title())


class GLiNER25Backend:
    """Zero-shot / joint extraction using Fastino GLiNER 2.5 boundary models."""

    name = "gliner25"

    def __init__(
        self,
        model_name: str | None = None,
        threshold: float = 0.3,
        enable_relations: bool = True,
        labels: list[str] | None = None,
        relations: list[str] | None = None,
        enable_joint: bool = False,
        mode: str = "local",
        hf_endpoint: str = "https://api-inference.huggingface.co/models",
        hf_token_env: str = "HF_TOKEN",
        pioneer_base_url: str = "https://api.pioneer.ai",
        pioneer_token_env: str = "PIONEER_API_KEY",
    ) -> None:
        self.model_name = model_name or os.getenv("GLINER25_MODEL", "fastino/gliner2.5-small-v1")
        self.threshold = threshold
        self.enable_relations = enable_relations
        self.labels = [label.lower() for label in (labels or DEFAULT_ENTITY_LABELS)]
        self.relations = relations or DEFAULT_RELATIONS
        self.enable_joint = enable_joint
        self.mode = (mode or "local").lower()
        self.hf_endpoint = hf_endpoint
        self.hf_token_env = hf_token_env
        self.pioneer_base_url = pioneer_base_url
        self.pioneer_token_env = pioneer_token_env
        self._extractor = None
        self._joint = None
        if self.mode == "local":
            self._load()

    def _load(self) -> None:
        try:
            from gliner2 import AutoExtractor
        except ImportError as exc:
            raise ImportError(
                "gliner2 is not installed. Run `pip install 'clinical-gliner-kg[gliner2]'` "
                "or `pip install 'gliner2[local]'`."
            ) from exc

        self._extractor = AutoExtractor.from_pretrained(self.model_name)
        if self.enable_relations and self.enable_joint:
            try:
                from gliner2.joint_ie import JointIE

                self._joint = JointIE.from_pretrained(self.model_name)
            except Exception:
                self._joint = None

    def extract(self, text: str) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
        if self.mode == "pioneer":
            from clinical_gliner_kg.backends.hosted import extract_pioneer

            return extract_pioneer(
                text,
                model=self.model_name,
                labels=self.labels,
                relations=self.relations if self.enable_relations else [],
                base_url=self.pioneer_base_url,
                token_env=self.pioneer_token_env,
                threshold=self.threshold,
            )
        if self.mode in {"huggingface_api", "huggingface", "hf"}:
            from clinical_gliner_kg.backends.hosted import extract_huggingface

            return extract_huggingface(
                text,
                model=self.model_name,
                labels=self.labels,
                endpoint=self.hf_endpoint,
                token_env=self.hf_token_env,
                threshold=self.threshold,
            )
        entities = self._extract_entities(text)
        relations = self._extract_relations(text, entities)
        return entities, relations

    def _extract_entities(self, text: str) -> list[ClinicalEntity]:
        assert self._extractor is not None
        raw = self._extractor.extract_entities(
            text,
            self.labels,
            include_spans=True,
            include_confidence=True,
        )
        grouped = raw.get("entities", raw) if isinstance(raw, dict) else {}
        entities: list[ClinicalEntity] = []
        counter = 0
        if isinstance(grouped, dict):
            for label, items in grouped.items():
                for item in _as_item_list(items):
                    surface, start, end, conf = _unpack_span(item, text)
                    if conf < self.threshold:
                        continue
                    entities.append(
                        ClinicalEntity(
                            id=f"ent_{counter}",
                            text=surface,
                            label=_normalize_label(str(label)),
                            start_char=start,
                            end_char=end,
                            confidence=conf,
                            source_model=self.model_name,
                        )
                    )
                    counter += 1
        return entities

    def _extract_relations(self, text: str, entities: list[ClinicalEntity]) -> list[ClinicalRelation]:
        if self._joint is not None:
            try:
                return self._joint_relations(text, entities)
            except Exception:
                pass
        assert self._extractor is not None
        try:
            raw = self._extractor.extract_relations(
                text,
                self.relations,
                include_confidence=True,
                include_spans=True,
            )
        except Exception:
            return []
        payload = raw.get("relation_extraction", raw) if isinstance(raw, dict) else {}
        relations: list[ClinicalRelation] = []
        if not isinstance(payload, dict):
            return relations
        for rel_name, pairs in payload.items():
            for pair in _as_item_list(pairs):
                subj_text, obj_text, conf, s0, s1, o0, o1 = _unpack_pair(pair)
                subj = _nearest(entities, subj_text, start=s0, end=s1)
                obj = _nearest(entities, obj_text, start=o0, end=o1)
                if not subj or not obj:
                    continue
                relations.append(
                    ClinicalRelation(
                        subject_id=subj.id,
                        relation=str(rel_name).upper(),
                        object_id=obj.id,
                        confidence=conf,
                        source_model=self.model_name,
                        subject_start=s0 if s0 is not None else subj.start_char,
                        subject_end=s1 if s1 is not None else subj.end_char,
                        object_start=o0 if o0 is not None else obj.start_char,
                        object_end=o1 if o1 is not None else obj.end_char,
                    )
                )
        return relations

    def _joint_relations(self, text: str, entities: list[ClinicalEntity]) -> list[ClinicalRelation]:
        assert self._joint is not None
        schema = (
            self._joint.create_schema()
            .entities(self.labels)
            .relation("HAS_CONDITION", "patient", "condition")
            .relation("TAKES", "patient", "medication")
            .relation("TREATS", "medication", "condition")
            .relation("HAS_VALUE", "laboratory_test", "laboratory_result")
        )
        result = self._joint.extract(text, schema)
        data = result.to_dict() if hasattr(result, "to_dict") else result
        relations: list[ClinicalRelation] = []
        rel_block = data.get("relations", data.get("relation_extraction", {})) if isinstance(data, dict) else {}
        if isinstance(rel_block, dict):
            for rel_name, pairs in rel_block.items():
                for pair in _as_item_list(pairs):
                    subj_text, obj_text, conf, s0, s1, o0, o1 = _unpack_pair(pair)
                    subj = _nearest(entities, subj_text, start=s0, end=s1)
                    obj = _nearest(entities, obj_text, start=o0, end=o1)
                    if subj and obj:
                        relations.append(
                            ClinicalRelation(
                                subject_id=subj.id,
                                relation=str(rel_name).upper(),
                                object_id=obj.id,
                                confidence=conf,
                                source_model=f"{self.model_name}+jointie",
                                subject_start=s0 if s0 is not None else subj.start_char,
                                subject_end=s1 if s1 is not None else subj.end_char,
                                object_start=o0 if o0 is not None else obj.start_char,
                                object_end=o1 if o1 is not None else obj.end_char,
                            )
                        )
        return relations


def _as_item_list(items: Any) -> list[Any]:
    if items is None:
        return []
    if isinstance(items, list):
        return items
    return [items]


def _unpack_span(item: Any, text: str) -> tuple[str, int, int, float]:
    if isinstance(item, str):
        start = text.lower().find(item.lower())
        end = start + len(item) if start >= 0 else 0
        return item, max(start, 0), max(end, 0), 0.80
    if isinstance(item, dict):
        surface = str(item.get("text") or item.get("span") or "")
        start = int(item.get("start", text.lower().find(surface.lower()) if surface else 0) or 0)
        end = int(item.get("end", start + len(surface)))
        conf = float(item.get("confidence", item.get("score", 0.80)))
        return surface, start, end, conf
    if isinstance(item, (list, tuple)) and item:
        return str(item[0]), 0, 0, 0.80
    return str(item), 0, 0, 0.50


def _span_from_arg(arg: Any) -> tuple[str, int | None, int | None]:
    if isinstance(arg, dict):
        text = str(arg.get("text") or arg.get("span") or "")
        start = arg.get("start")
        end = arg.get("end")
        return text, (int(start) if start is not None else None), (int(end) if end is not None else None)
    return str(arg or ""), None, None


def _unpack_pair(item: Any) -> tuple[str, str, float, int | None, int | None, int | None, int | None]:
    if isinstance(item, dict):
        head = item.get("head") or item.get("subject") or item.get("source") or ""
        tail = item.get("tail") or item.get("object") or item.get("target") or ""
        head_text, hs, he = _span_from_arg(head)
        tail_text, ts, te = _span_from_arg(tail)
        if hs is None and item.get("head_start") is not None:
            hs, he = int(item["head_start"]), int(item.get("head_end") or 0)
        if ts is None and item.get("tail_start") is not None:
            ts, te = int(item["tail_start"]), int(item.get("tail_end") or 0)
        conf = float(item.get("confidence", item.get("score", 0.80)))
        return head_text, tail_text, conf, hs, he, ts, te
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        conf = float(item[2]) if len(item) > 2 and isinstance(item[2], (int, float)) else 0.80
        return str(item[0]), str(item[1]), conf, None, None, None, None
    return "", "", 0.0, None, None, None, None


def _overlaps(start: int, end: int, ent: ClinicalEntity) -> bool:
    return not (end <= ent.start_char or start >= ent.end_char)


def _nearest(
    entities: list[ClinicalEntity],
    surface: str,
    start: int | None = None,
    end: int | None = None,
) -> ClinicalEntity | None:
    if not surface and start is None:
        return None
    if start is not None and end is not None:
        exact = [ent for ent in entities if ent.start_char == start and ent.end_char == end]
        if exact:
            return exact[0]
        overlapping = [ent for ent in entities if _overlaps(start, end, ent)]
        if len(overlapping) == 1:
            return overlapping[0]
        if overlapping and surface:
            needle = surface.lower()
            for ent in overlapping:
                if ent.text.lower() == needle:
                    return ent
            return overlapping[0]
    if not surface:
        return None
    needle = surface.lower()
    exact_text = [ent for ent in entities if ent.text.lower() == needle]
    if len(exact_text) == 1:
        return exact_text[0]
    if start is not None and exact_text:
        return min(exact_text, key=lambda ent: abs(ent.start_char - start))
    if exact_text:
        return exact_text[-1]
    for ent in entities:
        if needle in ent.text.lower() or ent.text.lower() in needle:
            return ent
    return None
