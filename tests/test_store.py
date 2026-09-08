from clinical_gliner_kg.graph.store import JsonlGraphStore
from clinical_gliner_kg.models import EventEnvelope
from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline


TEXT = "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%."


def test_jsonl_upsert_is_idempotent(tmp_path):
    store = JsonlGraphStore(tmp_path / "assertions.jsonl")
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    env = EventEnvelope(document_id="n1", payload=TEXT, source="test")
    pipeline.process_and_upsert(env, store)
    first = store.load()
    assert first
    pipeline.process_and_upsert(env, store)
    second = store.load()
    assert set(first) == set(second)
    linked = [row for row in second.values() if row["kind"] == "entity" and row["payload"].get("terminology")]
    assert linked
    assert linked[0]["payload"]["terminology"]["version"]
    rels = [row for row in second.values() if row["kind"] == "relation"]
    assert any(row["payload"]["history"] for row in rels)
