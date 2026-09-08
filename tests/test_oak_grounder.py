from clinical_gliner_kg.components.oak_grounder import OaklibGrounder
from clinical_gliner_kg.components.ontology_linker import OntologyValidationEngine
from clinical_gliner_kg.models import ClinicalEntity


def test_oak_grounder_skips_missing_sqlite_selector():
    grounder = OaklibGrounder(adapters_by_label={"Condition": ["sqlite:obo:does-not-exist"]})
    assert grounder.available == []
    ent = ClinicalEntity(id="e", text="type 2 diabetes", label="Condition", start_char=0, end_char=15, confidence=0.9)
    assert grounder.ground(ent).terminology is None


def test_oak_simpleobo_grounds_diabetes():
    grounder = OaklibGrounder()
    if not grounder.available:
        return
    ent = ClinicalEntity(id="e", text="type 2 diabetes", label="Disease", start_char=0, end_char=15, confidence=0.9)
    linked = grounder.ground(ent)
    assert linked.terminology is not None
    assert linked.terminology.system == "MONDO"
    assert linked.terminology.method.startswith("oaklib")


def test_catalog_still_links_without_oak():
    engine = OntologyValidationEngine()
    ent = ClinicalEntity(id="e", text="metformin", label="Medication", start_char=0, end_char=9, confidence=0.9)
    linked = engine.link_entity(ent)
    assert linked.terminology is not None
    assert linked.terminology.system == "RxNorm"
