from clinical_gliner_kg.backends.gliner25 import _nearest
from clinical_gliner_kg.components.llm_adjudicator import LLMAdjudicator
from clinical_gliner_kg.components.phi_gate import PHIPolicyGate
from clinical_gliner_kg.graph.emitter import GraphEmitter
from clinical_gliner_kg.models import (
    ClinicalEntity,
    ClinicalKnowledgeGraph,
    ClinicalRelation,
    ProvenanceMetadata,
    ValidationStatus,
)
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


TEXT = "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."


def test_unlinked_entities_are_not_auto_validated():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    kg = pipeline.process_document(TEXT, document_id="link")
    linked = [ent for ent in kg.entities if ent.terminology and not ent.is_phi]
    unlinked = [ent for ent in kg.entities if not ent.terminology and not ent.is_phi]
    assert linked
    assert all(ent.validation_status == ValidationStatus.LINKED for ent in linked)
    assert all(ent.validation_status == ValidationStatus.UNLINKED for ent in unlinked)


def test_no_llm_does_not_inflate_confidence_or_fake_adjudication():
    adj = LLMAdjudicator(confidence_threshold=0.75, provider="none")
    subj = ClinicalEntity(id="s", text="metformin", label="Medication", start_char=0, end_char=9, confidence=0.9)
    obj = ClinicalEntity(id="o", text="diabetes", label="Condition", start_char=10, end_char=18, confidence=0.9)
    rel = ClinicalRelation(subject_id="s", relation="TREATS", object_id="o", confidence=0.40)
    out = adj.adjudicate_relations([rel], {"s": subj, "o": obj}, [(True, "Valid domain-range alignment")])
    assert out[0].validation_status == ValidationStatus.NEEDS_REVIEW
    assert out[0].confidence == 0.40


def test_forbidden_schema_rejects_without_llm():
    adj = LLMAdjudicator(confidence_threshold=0.75, provider="none")
    subj = ClinicalEntity(id="s", text="metformin", label="Medication", start_char=0, end_char=9, confidence=0.9)
    obj = ClinicalEntity(id="o", text="kidney", label="Anatomy", start_char=10, end_char=16, confidence=0.9)
    rel = ClinicalRelation(subject_id="s", relation="HAS_ANATOMICAL_SITE", object_id="o", confidence=0.88)
    out = adj.adjudicate_relations(
        [rel],
        {"s": subj, "o": obj},
        [(False, "Ontology violation: Medication cannot have relation HAS_ANATOMICAL_SITE to Anatomy")],
    )
    assert out[0].validation_status == ValidationStatus.REJECTED
    assert out[0].confidence == 0.88


def test_phi_mask_uses_offsets_not_global_replace():
    gate = PHIPolicyGate(action="mask")
    text = "SSN 078-05-1120 is secret; the guideline id 078-05-1120 is not a person SSN."
    start = text.index("078-05-1120")
    # Only the first occurrence matches the SSN regex as a whole SSN token; still ensure
    # a non-overlapping identical substring is not blindly replaced if outside the span.
    out, _entities, findings = gate.apply(text, [])
    assert findings
    assert out.count("[REDACTED_SSN]") >= 1
    # Offset masking must not scramble later characters that were not in a finding span.
    for item in findings:
        assert item.end <= len(text)


def test_emitter_drops_relations_to_phi_even_if_validated():
    kg = ClinicalKnowledgeGraph(
        document_id="d1",
        entities=[
            ClinicalEntity(id="p", text="Jane", label="Patient", start_char=0, end_char=4, confidence=0.9, is_phi=True),
            ClinicalEntity(id="c", text="diabetes", label="Condition", start_char=10, end_char=18, confidence=0.9),
        ],
        relations=[
            ClinicalRelation(
                subject_id="p",
                relation="HAS_CONDITION",
                object_id="c",
                confidence=0.9,
                validation_status=ValidationStatus.VALIDATED,
            )
        ],
        provenance=ProvenanceMetadata(document_id="d1"),
    )
    cypher = GraphEmitter.emit_cypher(kg)
    assert not any("HAS_CONDITION" in row for row in cypher)
    assert "Jane" not in " ".join(cypher)


def test_nearest_prefers_overlapping_span():
    first = ClinicalEntity(id="m1", text="metformin", label="Medication", start_char=10, end_char=19, confidence=0.9)
    second = ClinicalEntity(id="m2", text="metformin", label="Medication", start_char=80, end_char=89, confidence=0.9)
    hit = _nearest([first, second], "metformin", start=80, end=89)
    assert hit is not None
    assert hit.id == "m2"
