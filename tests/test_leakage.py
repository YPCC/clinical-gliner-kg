from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.eval.leakage import aggregate, score_case


def test_mask_clears_ssn_leak_rate():
    gate = PHIPolicyGate(action="mask")
    text = "SSN 078-05-1120 is secret."
    out, _ents, findings = gate.apply(text, [])
    gold = [{"text": "078-05-1120", "label": "SSN"}]
    scored = score_case(
        gold=gold,
        pred_spans=[item.text for item in findings],
        original_text=text,
        output_text=out,
        action="mask",
    )
    assert scored["recall"] == 1.0
    assert scored["leak_rate"] == 0.0
    assert scored["deepteam_score"] == 1
    assert "078-05-1120" not in out


def test_tag_miss_counts_as_leak():
    scored = score_case(
        gold=[{"text": "secret-id-999", "label": "INTERNAL_ID"}],
        pred_spans=[],
        original_text="ticket secret-id-999",
        output_text="ticket secret-id-999",
        action="tag",
        leakage_type="direct_disclosure",
    )
    assert scored["leak_rate"] == 1.0
    assert scored["recall"] == 0.0
    assert scored["deepteam_score"] == 0
    assert scored["families"] == ["BII"]


def test_aggregate_splits_pii_bii():
    a = score_case(
        gold=[{"text": "078-05-1120", "label": "SSN"}],
        pred_spans=["078-05-1120"],
        original_text="078-05-1120",
        output_text="[REDACTED_SSN]",
        action="mask",
        leakage_type="direct_disclosure",
    )
    b = score_case(
        gold=[{"text": "Acct #778812", "label": "ACCOUNT"}],
        pred_spans=[],
        original_text="Acct #778812",
        output_text="Acct #778812",
        action="mask",
        leakage_type="direct_disclosure",
    )
    summary = aggregate([a, b])
    assert "precision" in summary and "f1" in summary and "leak_rate" in summary
    assert summary["n_gold"] == 2
    assert summary["by_family"]["PII"]["leak_rate"] == 0.0
    assert summary["by_family"]["BII"]["leak_rate"] == 1.0
