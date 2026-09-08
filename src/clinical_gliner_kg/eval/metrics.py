"""Span-level precision / recall helpers for the architecture spike."""

from __future__ import annotations

from collections import defaultdict


def normalize(text: str) -> str:
    collapsed = " ".join(text.lower().replace("-", " ").split())
    return collapsed


def prf(true_pos: int, pred_pos: int, gold_pos: int) -> dict[str, float]:
    precision = true_pos / pred_pos if pred_pos else 0.0
    recall = true_pos / gold_pos if gold_pos else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": true_pos, "pred": pred_pos, "gold": gold_pos}


def entity_prf(pred_spans: list[tuple[str, str]], gold_spans: list[tuple[str, str]]) -> dict[str, float]:
    pred = {(normalize(text), label) for text, label in pred_spans}
    gold = {(normalize(text), label) for text, label in gold_spans}
    return prf(len(pred & gold), len(pred), len(gold))


def entity_prf_by_label(
    pred_spans: list[tuple[str, str]],
    gold_spans: list[tuple[str, str]],
) -> dict[str, dict[str, float]]:
    pred_map: dict[str, set[str]] = defaultdict(set)
    gold_map: dict[str, set[str]] = defaultdict(set)
    for text, label in pred_spans:
        pred_map[label].add(normalize(text))
    for text, label in gold_spans:
        gold_map[label].add(normalize(text))
    labels = sorted(set(pred_map) | set(gold_map))
    return {label: prf(len(pred_map[label] & gold_map[label]), len(pred_map[label]), len(gold_map[label])) for label in labels}


def relation_prf(pred: list[tuple[str, str, str]], gold: list[tuple[str, str, str]]) -> dict[str, float]:
    pset = {(normalize(s), r.upper(), normalize(o)) for s, r, o in pred}
    gset = {(normalize(s), r.upper(), normalize(o)) for s, r, o in gold}
    return prf(len(pset & gset), len(pset), len(gset))
