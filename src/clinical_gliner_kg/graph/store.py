"""Idempotent JSONL assertion store — the disk stand-in for a living KG."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clinical_gliner_kg.models import ClinicalKnowledgeGraph, ValidationStatus

_RETRACT = {ValidationStatus.REJECTED, ValidationStatus.LLM_REJECTED}


class JsonlGraphStore:
    """Last-write-wins JSONL keyed by assertion idempotency_key.

    Re-processing the same document_id retracts keys that disappeared.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        if not self.path.exists():
            return records
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            records[row["key"]] = row
        return {key: row for key, row in records.items() if not row.get("retracted")}

    def upsert(self, kg: ClinicalKnowledgeGraph) -> dict[str, int]:
        existing = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    existing[row["key"]] = row
        now = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()
        written = 0
        updated = 0
        skipped = 0
        with self.path.open("a", encoding="utf-8") as handle:
            for ent in kg.entities:
                if ent.is_phi or not ent.idempotency_key:
                    continue
                payload = ent.model_dump()
                action = _write_row(
                    handle,
                    existing,
                    key=ent.idempotency_key,
                    kind="entity",
                    document_id=kg.document_id,
                    payload=payload,
                    now=now,
                )
                seen.add(ent.idempotency_key)
                written += action == "insert"
                updated += action == "update"
                skipped += action == "skip"
            for rel in kg.relations:
                if not rel.idempotency_key:
                    continue
                retract = rel.validation_status in _RETRACT
                payload = rel.model_dump()
                action = _write_row(
                    handle,
                    existing,
                    key=rel.idempotency_key,
                    kind="relation",
                    document_id=kg.document_id,
                    payload=payload,
                    now=now,
                    retracted=retract,
                )
                seen.add(rel.idempotency_key)
                written += action == "insert"
                updated += action == "update"
                skipped += action == "skip"
            retracted = 0
            for key, row in existing.items():
                if row.get("document_id") == kg.document_id and key not in seen and not row.get("retracted"):
                    handle.write(
                        json.dumps(
                            {**row, "retracted": True, "updated_at": now, "reason": "absent-on-reprocess"}
                        )
                        + "\n"
                    )
                    retracted += 1
        return {"insert": written, "update": updated, "skip": skipped, "retract": retracted}


def _write_row(
    handle,
    existing: dict[str, dict[str, Any]],
    *,
    key: str,
    kind: str,
    document_id: str,
    payload: dict[str, Any],
    now: str,
    retracted: bool = False,
) -> str:
    row = {
        "key": key,
        "kind": kind,
        "document_id": document_id,
        "payload": payload,
        "updated_at": now,
        "retracted": retracted,
    }
    prev = existing.get(key)
    if prev and prev.get("payload") == payload and prev.get("retracted") == retracted:
        return "skip"
    handle.write(json.dumps(row) + "\n")
    existing[key] = row
    return "update" if prev else "insert"
