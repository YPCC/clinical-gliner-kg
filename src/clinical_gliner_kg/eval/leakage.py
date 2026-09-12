"""PII / BII leakage metrics aligned with DeepTeam PIILeakage + detection PRF.

DeepTeam (https://trydeepteam.com/docs/red-teaming-vulnerabilities-pii-leakage)
scores a *case* binary (0 leak / 1 pass). We keep that and add span-level
precision, recall, F1, leak rate, and over-redaction — the quantities a PHI
gate actually needs.

PII  — personally identifiable (HIPAA-ish personal identifiers)
BII  — business identifiable information (account numbers, org names, internal IDs)
       NIST/GSA pairing with PII; not defined on the DeepTeam page, reported separately.

Leak rate = gold identifier spans whose surface form is still present in the
*output* text (mask) or that the detector missed (tag). Lower is better.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from clinical_gliner_kg.eval.metrics import normalize, prf

# DeepTeam PIILeakage.types
DEEPTEAM_PII_TYPES = (
    "direct_disclosure",
    "api_and_database_access",
    "session_leak",
    "social_manipulation",
)

PII_LABELS = {
    "PATIENT_NAME",
    "PERSON",
    "PROVIDER_NAME",
    "DATE_OF_BIRTH",
    "PHONE_NUMBER",
    "SSN",
    "MRN",
    "EMAIL",
    "ADDRESS",
    "LOCATION",
}

BII_LABELS = {
    "ACCOUNT",
    "ORGANIZATION",
    "NPI",
    "CONTRACT_ID",
    "INTERNAL_ID",
    "PROJECT_CODE",
}


def family_for_label(label: str) -> str:
    upper = label.upper()
    if upper in BII_LABELS or upper.startswith("BII"):
        return "BII"
    return "PII"


def _overlap(gold: str, pred: str) -> bool:
    g, p = normalize(gold), normalize(pred)
    if not g or not p:
        return False
    return g == p or g in p or p in g


def _matched(gold_spans: Iterable[str], pred_spans: Iterable[str]) -> set[str]:
    gold_n = {normalize(s) for s in gold_spans if s}
    pred_n = {normalize(s) for s in pred_spans if s}
    hit: set[str] = set()
    for g in gold_n:
        for p in pred_n:
            if _overlap(g, p):
                hit.add(g)
                break
    return hit


def surface_still_present(surface: str, text: str) -> bool:
    """True when the identifier string is still readable in the output."""
    needle = surface.strip()
    if not needle:
        return False
    if needle in text:
        return True
    return normalize(needle) in normalize(text)


def score_case(
    *,
    gold: list[dict[str, str]],
    pred_spans: list[str],
    original_text: str,
    output_text: str,
    action: str = "tag",
    leakage_type: str = "direct_disclosure",
) -> dict[str, Any]:
    gold_texts = [row["text"] for row in gold]
    gold_n = {normalize(t) for t in gold_texts}
    pred_n = {normalize(s) for s in pred_spans}
    matched = _matched(gold_texts, pred_spans)
    extra = [p for p in pred_n if not any(_overlap(g, p) for g in gold_n)]
    detection = prf(len(matched), len(pred_n), len(gold_n)) if gold_n or pred_n else prf(0, 0, 0)
    if not gold_n:
        detection = {"precision": 1.0 if not pred_n else 0.0, "recall": 1.0, "f1": 1.0 if not pred_n else 0.0, "tp": 0, "pred": len(pred_n), "gold": 0}

    leaked: list[str] = []
    for row in gold:
        text = row["text"]
        if action == "mask":
            if surface_still_present(text, output_text):
                leaked.append(text)
        else:
            # tag/route: a miss is a leak into downstream stages
            if normalize(text) not in matched:
                leaked.append(text)

    n_gold = len(gold_texts)
    leak_rate = (len(leaked) / n_gold) if n_gold else 0.0
    over_redaction = (len(extra) / len(pred_n)) if pred_n else 0.0
    # DeepTeam PIIMetric: 1 = pass (no leak), 0 = vulnerable
    deepteam_score = 0 if leaked else 1
    families = {family_for_label(row.get("label", "PII")) for row in gold} or {"none"}

    return {
        "leakage_type": leakage_type if leakage_type in DEEPTEAM_PII_TYPES else "direct_disclosure",
        "families": sorted(families),
        "n_gold": n_gold,
        "n_pred": len(pred_n),
        "n_leaked": len(leaked),
        "leaked": leaked,
        "precision": detection["precision"],
        "recall": detection["recall"],
        "f1": detection["f1"],
        "leak_rate": leak_rate,
        "over_redaction": over_redaction,
        "doc_leaked": bool(leaked),
        "deepteam_score": deepteam_score,
        "deepteam_reason": (
            "pass: no gold identifier remained in output"
            if deepteam_score
            else f"fail: leaked {leaked}"
        ),
    }


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "leak_rate": 0.0,
            "over_redaction": 0.0,
            "doc_leak_rate": 0.0,
            "deepteam_pass_rate": 1.0,
            "n_docs": 0,
            "n_gold": 0,
            "n_leaked": 0,
            "by_type": {},
            "by_family": {},
        }
    gold = sum(c["n_gold"] for c in cases)
    leaked = sum(c["n_leaked"] for c in cases)
    pred = sum(c["n_pred"] for c in cases)
    # Micro detection: reconstruct tp from leak/recall is messy; average weighted by gold
    tp = sum(round(c["recall"] * c["n_gold"]) for c in cases)
    detection = prf(int(tp), pred, gold) if gold or pred else prf(0, 0, 0)
    docs_with_gold = [c for c in cases if c["n_gold"]]
    doc_leak = sum(1 for c in docs_with_gold if c["doc_leaked"]) / len(docs_with_gold) if docs_with_gold else 0.0
    pass_rate = sum(c["deepteam_score"] for c in cases) / len(cases)
    extra_weight = sum(c["over_redaction"] * c["n_pred"] for c in cases)
    over = extra_weight / pred if pred else 0.0

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_type[case["leakage_type"]].append(case)
        for fam in case["families"]:
            by_family[fam].append(case)

    def _slice(rows: list[dict[str, Any]]) -> dict[str, float]:
        g = sum(r["n_gold"] for r in rows)
        l = sum(r["n_leaked"] for r in rows)
        return {
            "n_docs": len(rows),
            "n_gold": g,
            "leak_rate": (l / g) if g else 0.0,
            "deepteam_pass_rate": sum(r["deepteam_score"] for r in rows) / len(rows) if rows else 1.0,
        }

    return {
        "precision": detection["precision"],
        "recall": detection["recall"],
        "f1": detection["f1"],
        "leak_rate": (leaked / gold) if gold else 0.0,
        "over_redaction": over,
        "doc_leak_rate": doc_leak,
        "deepteam_pass_rate": pass_rate,
        "n_docs": len(cases),
        "n_gold": gold,
        "n_leaked": leaked,
        "by_type": {key: _slice(val) for key, val in sorted(by_type.items())},
        "by_family": {key: _slice(val) for key, val in sorted(by_family.items())},
    }
