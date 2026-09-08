from clinical_gliner_kg.graph.emitter import GraphEmitter
from clinical_gliner_kg.models import (
    ClinicalEntity,
    ClinicalKnowledgeGraph,
    ClinicalRelation,
    ProvenanceMetadata,
    TerminologyLink,
    ValidationStatus,
)


def test_emitter_skips_rejected_and_phi():
    kg = ClinicalKnowledgeGraph(
        document_id="d1",
        entities=[
            ClinicalEntity(
                id="m",
                text="metformin",
                label="Medication",
                start_char=0,
                end_char=9,
                confidence=0.9,
                terminology=TerminologyLink(system="RxNorm", code="6809", display="Metformin", match_score=1.0),
            ),
            ClinicalEntity(
                id="phi",
                text="jane@example.org",
                label="EMAIL",
                start_char=20,
                end_char=36,
                confidence=0.99,
                is_phi=True,
            ),
        ],
        relations=[
            ClinicalRelation(
                subject_id="m",
                relation="HAS_ANATOMICAL_SITE",
                object_id="phi",
                confidence=0.2,
                validation_status=ValidationStatus.REJECTED,
            )
        ],
        provenance=ProvenanceMetadata(document_id="d1"),
    )
    cypher = GraphEmitter.emit_cypher(kg)
    assert any("Medication" in row for row in cypher)
    assert not any("jane@" in row for row in cypher)
    assert not any("HAS_ANATOMICAL_SITE" in row for row in cypher)
    ttl = GraphEmitter.emit_turtle(kg)
    assert "ex:m" in ttl
    assert "HAS_ANATOMICAL_SITE" not in ttl
