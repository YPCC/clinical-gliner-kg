from clinical_gliner_kg.components.ontology_linker import OntologyValidationEngine
from clinical_gliner_kg.models import ClinicalEntity, ClinicalRelation


def _ents():
    return {
        "p": ClinicalEntity(id="p", text="Patient", label="Patient", start_char=0, end_char=7, confidence=0.9),
        "c": ClinicalEntity(
            id="c", text="type 2 diabetes", label="Condition", start_char=13, end_char=28, confidence=0.9
        ),
        "m": ClinicalEntity(id="m", text="metformin", label="Medication", start_char=46, end_char=55, confidence=0.9),
        "a": ClinicalEntity(id="a", text="kidney", label="Anatomy", start_char=80, end_char=86, confidence=0.8),
    }


def test_links_known_terms():
    engine = OntologyValidationEngine()
    linked = engine.link_entity(_ents()["m"])
    assert linked.terminology is not None
    assert linked.terminology.system == "RxNorm"
    assert linked.terminology.code == "6809"


def test_allows_treats():
    engine = OntologyValidationEngine()
    ents = _ents()
    ok, _ = engine.validate_relation(
        ClinicalRelation(subject_id="m", relation="TREATS", object_id="c", confidence=0.9),
        ents,
    )
    assert ok is True


def test_forbids_medication_anatomical_site():
    engine = OntologyValidationEngine()
    ents = _ents()
    ok, comment = engine.validate_relation(
        ClinicalRelation(subject_id="m", relation="HAS_ANATOMICAL_SITE", object_id="a", confidence=0.4),
        ents,
    )
    assert ok is False
    assert "Ontology violation" in comment
