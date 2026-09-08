"""Literature + PHI architecture metrics."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field

from clinical_gliner_kg.eval.metrics import entity_prf, normalize, prf, relation_prf
from clinical_gliner_kg.models import ClinicalKnowledgeGraph


LABEL_ALIASES = {
    "disease": "Disease",
    "condition": "Disease",
    "chemical": "Chemical",
    "medication": "Chemical",
    "drug": "Chemical",
}


def canon_label(label: str) -> str:
    return LABEL_ALIASES.get(label.strip().lower(), label)


def kg_entity_spans(kg: ClinicalKnowledgeGraph) -> list[tuple[str, str]]:
    return [(ent.text, canon_label(ent.label)) for ent in kg.entities if not ent.is_phi]


def gold_entity_spans(entities: list[dict]) -> list[tuple[str, str]]:
    return [(row["text"], canon_label(row["label"])) for row in entities]


def kg_relations(kg: ClinicalKnowledgeGraph) -> list[tuple[str, str, str]]:
    id_to_text = {ent.id: ent.text for ent in kg.entities}
    out = []
    for rel in kg.relations:
        if rel.validation_status.value == "REJECTED":
            continue
        out.append(
            (
                id_to_text.get(rel.subject_id, rel.subject_id),
                rel.relation,
                id_to_text.get(rel.object_id, rel.object_id),
            )
        )
    return out


def ontology_pass_rate(kg: ClinicalKnowledgeGraph) -> dict[str, float]:
    rels = [rel for rel in kg.relations]
    if not rels:
        linked = sum(1 for ent in kg.entities if ent.terminology)
        total = len([ent for ent in kg.entities if not ent.is_phi])
        return {
            "relation_pass": 1.0,
            "entity_linked": linked / total if total else 0.0,
            "n_relations": 0,
            "n_entities": total,
        }
    passed = sum(1 for rel in rels if rel.validation_status.value in {"VALIDATED", "ADJUDICATED"})
    linked = sum(1 for ent in kg.entities if ent.terminology)
    total = len([ent for ent in kg.entities if not ent.is_phi])
    return {
        "relation_pass": passed / len(rels),
        "entity_linked": linked / total if total else 0.0,
        "n_relations": len(rels),
        "n_entities": total,
    }


def phi_scores(pred_spans: list[str], gold_spans: list[str]) -> dict[str, float]:
    pred = {normalize(s) for s in pred_spans}
    gold = {normalize(s) for s in gold_spans}
    matched = set()
    for g in gold:
        for p in pred:
            if g in p or p in g:
                matched.add(g)
                break
    extra = [p for p in pred if not any(g in p or p in g for g in gold)]
    scores = prf(len(matched), len(pred), len(gold))
    scores["over_redaction"] = len(extra) / len(pred) if pred else 0.0
    scores["recall"] = len(matched) / len(gold) if gold else 1.0
    return scores


@dataclass
class LatencyBudget:
    seconds: list[float] = field(default_factory=list)

    def add(self, value: float) -> None:
        self.seconds.append(value)

    def summary(self) -> dict[str, float]:
        if not self.seconds:
            return {"n": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "docs_per_sec": 0.0}
        ordered = sorted(self.seconds)
        p95_idx = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
        total = sum(self.seconds)
        return {
            "n": len(ordered),
            "mean": statistics.mean(ordered),
            "p50": statistics.median(ordered),
            "p95": ordered[p95_idx],
            "docs_per_sec": len(ordered) / total if total else 0.0,
        }


def estimate_cost_per_document(
    latency: dict[str, float],
    escalation_rate: float,
    cpu_hour_usd: float = 0.40,
    llm_usd_per_doc: float = 0.012,
) -> dict[str, float]:
    """Transparent planning model, not a vendor invoice.

    Local encoder cost = wall time * assumed CPU-hour rate.
    Escalated documents add an LLM adjudication fee.
    """
    mean_s = latency.get("mean") or 0.0
    local = mean_s / 3600.0 * cpu_hour_usd
    llm = escalation_rate * llm_usd_per_doc
    per_doc = local + llm
    return {
        "usd_per_doc": per_doc,
        "usd_per_100k": per_doc * 100_000,
        "local_usd_per_doc": local,
        "llm_usd_per_doc": llm,
        "escalation_rate": escalation_rate,
        "cpu_hour_usd": cpu_hour_usd,
        "llm_usd_per_escalated_doc": llm_usd_per_doc,
    }


def timed(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start
