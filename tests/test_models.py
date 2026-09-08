from clinical_gliner_kg.models import ClinicalEntity, ValidationStatus


def test_entity_defaults():
    ent = ClinicalEntity(
        id="e1",
        text="metformin",
        label="Medication",
        start_char=0,
        end_char=9,
        confidence=0.9,
    )
    assert ent.is_phi is False
    assert ent.validation_status == ValidationStatus.CANDIDATE
