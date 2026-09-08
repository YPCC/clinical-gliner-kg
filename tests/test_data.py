from clinical_gliner_kg.data import load_medical_data_catalog, load_synthetic_clinical_notes
from clinical_gliner_kg.eval.metrics import entity_prf


def test_synthetic_notes_load():
    notes = load_synthetic_clinical_notes()
    assert len(notes) >= 6
    assert "metformin" in notes[0]["text"]


def test_catalog_marks_dua_datasets():
    catalog = load_medical_data_catalog()
    names = {row["name"] for row in catalog["datasets"]}
    assert "NCBI Disease Corpus" in names
    assert "BC5CDR" in names
    assert any(row.get("access") == "dua" for row in catalog["datasets"])


def test_entity_prf_exact():
    scores = entity_prf([("Metformin", "Medication")], [("metformin", "Medication")])
    assert scores["f1"] == 1.0
