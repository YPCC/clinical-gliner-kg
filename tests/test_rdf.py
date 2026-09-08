from clinical_gliner_kg.graph.rdf import RdfEmitter
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline
from clinical_gliner_kg.settings import GraphSettings, RdfsSettings


TEXT = "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."


def test_rdfs_graph_has_treats_and_assertion_prov():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    pipeline.settings.graph = GraphSettings(target="rdfs")
    pipeline.emitter.settings = pipeline.settings.graph
    kg = pipeline.process_document(TEXT, document_id="rdf1")
    assert "clin:treats" in kg.turtle or "treats" in kg.turtle
    assert "clin:Assertion" in kg.turtle
    assert "prov:" in kg.turtle
    assert kg.sparql["treats"]
    labels = {(row["medLabel"], row["condLabel"]) for row in kg.sparql["treats"]}
    assert any("metformin" in med.lower() and "diabetes" in cond.lower() for med, cond in labels)


def test_lpg_only_skips_sparql():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    pipeline.settings.graph = GraphSettings(target="lpg")
    pipeline.emitter.settings = pipeline.settings.graph
    kg = pipeline.process_document(TEXT, document_id="lpg1")
    assert kg.cypher_queries
    assert kg.sparql == {}
    assert kg.json_ld["@id"] == "urn:doc:lpg1"


def test_rdflib_sparql_direct():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    kg = pipeline.process_document(TEXT, document_id="rdf2")
    rows = RdfEmitter(RdfsSettings()).query(
        kg,
        """
        PREFIX clin: <https://ypcc.dev/clinical-gliner-kg/ontology#>
        SELECT ?s WHERE { ?s a clin:Medication }
        """,
    )
    assert rows
