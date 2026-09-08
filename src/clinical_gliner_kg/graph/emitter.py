"""Emit Cypher, JSON-LD, and Turtle with provenance."""

from __future__ import annotations

from clinical_gliner_kg.models import ClinicalKnowledgeGraph, ValidationStatus

_DROP_REL = {
    ValidationStatus.REJECTED,
    ValidationStatus.LLM_REJECTED,
}


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _safe_ids(graph: ClinicalKnowledgeGraph) -> set[str]:
    return {ent.id for ent in graph.entities if not ent.is_phi}


def _emit_relation(rel, safe: set[str]) -> bool:
    if rel.validation_status in _DROP_REL:
        return False
    return rel.subject_id in safe and rel.object_id in safe


class GraphEmitter:
    @staticmethod
    def emit_cypher(graph: ClinicalKnowledgeGraph) -> list[str]:
        queries: list[str] = []
        meta = graph.provenance
        safe = _safe_ids(graph)
        for ent in graph.entities:
            if ent.is_phi or ent.id not in safe:
                continue
            code = ent.terminology.code if ent.terminology else "UNLINKED"
            system = ent.terminology.system if ent.terminology else "NONE"
            queries.append(
                "MERGE (e:"
                + ent.label
                + " {id: '"
                + _esc(ent.id)
                + "'}) "
                + "ON CREATE SET e.name = '"
                + _esc(ent.text)
                + "', e.code = '"
                + _esc(code)
                + "', e.system = '"
                + _esc(system)
                + "', e.doc_id = '"
                + _esc(meta.document_id)
                + "', e.confidence = "
                + f"{ent.confidence:.3f}"
                + ", e.link_conf = "
                + f"{ent.linking_confidence:.3f}"
                + ", e.model = '"
                + _esc(ent.source_model)
                + "', e.status = '"
                + ent.validation_status.value
                + "'"
            )
        for rel in graph.relations:
            if not _emit_relation(rel, safe):
                continue
            queries.append(
                "MATCH (s {id: '"
                + _esc(rel.subject_id)
                + "'}), (o {id: '"
                + _esc(rel.object_id)
                + "'}) "
                + "MERGE (s)-[r:"
                + rel.relation
                + " {confidence: "
                + f"{rel.confidence:.3f}"
                + ", status: '"
                + rel.validation_status.value
                + "', doc_id: '"
                + _esc(meta.document_id)
                + "'}]->(o)"
            )
        return queries

    @staticmethod
    def emit_json_ld(graph: ClinicalKnowledgeGraph) -> dict:
        safe = _safe_ids(graph)
        return {
            "@context": {
                "snomed": "http://snomed.info/id/",
                "rxnorm": "http://purl.bioontology.org/ontology/RXNORM/",
                "loinc": "http://loinc.org/rdf/",
                "prov": "http://www.w3.org/ns/prov#",
                "schema": "https://schema.org/",
            },
            "@id": f"urn:doc:{graph.document_id}",
            "prov:generatedAtTime": graph.provenance.extracted_at,
            "prov:wasDerivedFrom": graph.document_id,
            "prov:wasGeneratedBy": graph.provenance.extraction_backend,
            "entities": [ent.model_dump() for ent in graph.entities if ent.id in safe],
            "relations": [rel.model_dump() for rel in graph.relations if _emit_relation(rel, safe)],
        }

    @staticmethod
    def emit_turtle(graph: ClinicalKnowledgeGraph) -> str:
        safe = _safe_ids(graph)
        lines = [
            "@prefix ex: <http://example.org/clinical/> .",
            "@prefix prov: <http://www.w3.org/ns/prov#> .",
            f"ex:{graph.document_id} a ex:ClinicalDocument ;",
            f'  prov:generatedAtTime "{graph.provenance.extracted_at}" .',
        ]
        for ent in graph.entities:
            if ent.id not in safe:
                continue
            lines.append(f"ex:{ent.id} a ex:{ent.label} ;")
            lines.append(f'  ex:prefLabel "{_esc(ent.text)}" ;')
            if ent.terminology:
                lines.append(f'  ex:code "{_esc(ent.terminology.system)}:{_esc(ent.terminology.code)}" ;')
            lines.append(f'  ex:status "{ent.validation_status.value}" ;')
            lines.append(f"  ex:confidence {ent.confidence:.3f} .")
        for rel in graph.relations:
            if not _emit_relation(rel, safe):
                continue
            lines.append(f"ex:{rel.subject_id} ex:{rel.relation} ex:{rel.object_id} .")
        return "\n".join(lines) + "\n"
