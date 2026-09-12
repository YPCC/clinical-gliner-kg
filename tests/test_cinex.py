from clinical_gliner_kg.pipeline import ClinicalSemanticExtractionPipeline
from clinical_gliner_kg.report.cinex import build_cinex_report


def test_cinex_report_has_29_items():
    pipeline = ClinicalSemanticExtractionPipeline(backend="heuristic")
    pipeline.settings.report.cinex = True
    kg = pipeline.process_document(
        "Patient with type 2 diabetes was started on metformin because HbA1c increased to 8.2%.",
        document_id="cinex1",
    )
    assert kg.cinex
    assert kg.cinex["url"] == "https://www.cinex-guideline.org/"
    assert kg.cinex["completeness"]["n_items"] == 29
    ids = [item["id"] for item in kg.cinex["items"]]
    assert ids[0] == "IM1"
    assert ids[-1] == "O5"
    assert kg.cinex["completeness"]["reported"] >= 10


def test_cinex_attaches_outcomes():
    report = build_cinex_report(None, None, outcomes={"f1": 0.48, "leak_rate": 0.1})
    o1 = next(item for item in report["items"] if item["id"] == "O1")
    assert o1["status"] == "reported"
    assert "0.48" in o1["response"]
