from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


TEXT = "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."


def test_heuristic_pipeline_extracts_core_graph():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    kg = pipeline.process_document(TEXT, document_id="t1")
    labels = {ent.label for ent in kg.entities}
    assert "Condition" in labels
    assert "Medication" in labels
    assert "Laboratory_Test" in labels
    assert any(ent.terminology and ent.terminology.system == "SNOMED-CT" for ent in kg.entities)
    assert any(ent.terminology and ent.terminology.system == "RxNorm" for ent in kg.entities)
    statuses = {rel.validation_status.value for rel in kg.relations}
    assert "VALIDATED" in statuses or "ADJUDICATED" in statuses
    assert kg.cypher_queries
    assert kg.json_ld["@id"] == "urn:doc:t1"
    assert kg.provenance.extraction_backend == "heuristic"


def test_rejects_impossible_anatomy_link_when_present():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic", confidence_threshold=0.85)
    text = TEXT + " Metformin was incorrectly associated with the kidney."
    kg = pipeline.process_document(text, document_id="t2")
    rejected = [rel for rel in kg.relations if rel.relation == "HAS_ANATOMICAL_SITE"]
    assert rejected
    assert all(rel.validation_status.value == "REJECTED" for rel in rejected)
