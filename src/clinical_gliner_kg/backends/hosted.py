"""Hosted GLiNER clients (Pioneer + Hugging Face Inference API)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 60) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc


def extract_pioneer(
    text: str,
    *,
    model: str,
    labels: list[str],
    relations: list[str],
    base_url: str,
    token_env: str,
    threshold: float,
) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
    key = os.getenv(token_env, "")
    if not key:
        raise RuntimeError(f"gliner.mode=pioneer requires ${token_env}")
    url = base_url.rstrip("/") + "/inference"
    payload = {
        "model_id": model,
        "text": text,
        "schema": {"entities": labels, "relations": relations},
        "threshold": threshold,
    }
    raw = _post_json(
        url,
        payload,
        {"X-API-Key": key, "Content-Type": "application/json"},
    )
    return _parse_hosted(raw, text, model, threshold)


def extract_huggingface(
    text: str,
    *,
    model: str,
    labels: list[str],
    endpoint: str,
    token_env: str,
    threshold: float,
) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
    token = os.getenv(token_env) or os.getenv("HUGGING_FACE_HUB_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or ""
    if not token:
        raise RuntimeError(f"gliner.mode=huggingface_api requires ${token_env}")
    url = endpoint.rstrip("/") + "/" + model.lstrip("/")
    raw = _post_json(
        url,
        {"inputs": text, "parameters": {"aggregation_strategy": "simple"}},
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return _parse_hosted(raw, text, model, threshold)


def _parse_hosted(
    raw: Any,
    text: str,
    model: str,
    threshold: float,
) -> tuple[list[ClinicalEntity], list[ClinicalRelation]]:
    entities: list[ClinicalEntity] = []
    relations: list[ClinicalRelation] = []
    grouped = raw
    if isinstance(raw, dict):
        grouped = raw.get("entities", raw.get("entity_extraction", raw))
        rel_block = raw.get("relations", raw.get("relation_extraction", {}))
        if isinstance(rel_block, dict):
            for name, pairs in rel_block.items():
                for pair in _as_list(pairs):
                    if isinstance(pair, dict):
                        relations.append(
                            ClinicalRelation(
                                subject_id=str(pair.get("head") or pair.get("subject") or ""),
                                relation=str(name).upper(),
                                object_id=str(pair.get("tail") or pair.get("object") or ""),
                                confidence=float(pair.get("confidence", pair.get("score", 0.8))),
                                source_model=model,
                            )
                        )
    counter = 0
    if isinstance(grouped, dict):
        for label, items in grouped.items():
            for item in _as_list(items):
                ent = _item_to_entity(item, label, text, model, counter, threshold)
                if ent:
                    entities.append(ent)
                    counter += 1
    elif isinstance(grouped, list):
        for item in grouped:
            label = str(item.get("entity_group") or item.get("label") or item.get("entity") or "Entity")
            ent = _item_to_entity(item, label, text, model, counter, threshold)
            if ent:
                entities.append(ent)
                counter += 1
    return entities, relations


def _item_to_entity(
    item: Any,
    label: str,
    text: str,
    model: str,
    index: int,
    threshold: float,
) -> ClinicalEntity | None:
    if isinstance(item, str):
        start = text.lower().find(item.lower())
        surface, start, end, conf = item, max(start, 0), max(start, 0) + len(item), 0.8
    elif isinstance(item, dict):
        surface = str(item.get("text") or item.get("word") or item.get("span") or "")
        start = int(item.get("start") or (text.lower().find(surface.lower()) if surface else 0) or 0)
        end = int(item.get("end") or start + len(surface))
        conf = float(item.get("confidence", item.get("score", 0.8)))
        label = str(item.get("label") or item.get("entity_group") or label)
    else:
        return None
    if conf < threshold or not surface:
        return None
    return ClinicalEntity(
        id=f"ent_{index}",
        text=surface,
        label=label.replace(" ", "_").title() if label.islower() else label,
        start_char=start,
        end_char=end,
        confidence=conf,
        source_model=model,
    )


def _as_list(items: Any) -> list[Any]:
    if items is None:
        return []
    if isinstance(items, list):
        return items
    return [items]
