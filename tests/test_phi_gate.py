from clinical_gliner_kg.components.phi_gate import PHIPolicyGate


def test_detects_email_phone_ssn():
    gate = PHIPolicyGate(action="tag")
    text = "Call 617-555-0198 or jane.rivera@example.org. SSN 078-05-1120."
    findings = gate.detect(text)
    labels = {item.label for item in findings}
    assert "EMAIL" in labels
    assert "PHONE_NUMBER" in labels
    assert "SSN" in labels


def test_mask_rewrites_text():
    gate = PHIPolicyGate(action="mask")
    text = "Email jane.rivera@example.org today."
    out, entities, findings = gate.apply(text, [])
    assert "[REDACTED_EMAIL]" in out
    assert findings
    assert all(ent.is_phi for ent in entities)
