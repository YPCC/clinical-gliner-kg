import json
from pathlib import Path

from clinical_gliner_kg.backends.gliner25 import _nearest
from clinical_gliner_kg.models import ClinicalEntity


def test_repeated_metformin_binds_to_span_not_first_mention():
    payload = json.loads((Path(__file__).parent / "data" / "relex_spans.json").read_text(encoding="utf-8"))
    entities = [ClinicalEntity(**item) for item in payload["entities"]]
    gold = payload["relations"][0]
    hit = _nearest(
        entities,
        gold["head"]["text"],
        start=gold["head"]["start"],
        end=gold["head"]["end"],
    )
    assert hit is not None
    assert hit.id == gold["expect_subject_id"]
    first = _nearest(entities, "metformin", start=32, end=41)
    assert first is not None
    assert first.id == "m1"
