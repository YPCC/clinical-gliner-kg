"""Emit LPG (Cypher) and/or RDFS (Turtle / JSON-LD / SPARQL) with provenance."""

from __future__ import annotations

from clinical_gliner_kg.models import ClinicalKnowledgeGraph, ValidationStatus
from clinical_gliner_kg.settings import GraphSettings

_DROP_REL = {
    ValidationStatus.REJECTED,
    ValidationStatus.LLM_REJECTED,
}


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _safe_ids(graph: ClinicalKnowledgeGraph) -> set[str]:
    return {ent.id for ent in graph.entities if not ent.is_phi}


def _emit_relation(rel, safe: set[str], emit_pending: bool = True) -> bool:
    if rel.validation_status in _DROP_REL:
        return False
    if not emit_pending and rel.validation_status == ValidationStatus.NEEDS_REVIEW:
        return False
    return rel.subject_id in safe and rel.object_id in safe


class GraphEmitter:
    def __init__(self, settings: GraphSettings | None = None) -> None:
        self.settings = settings or GraphSettings()

    def populate(self, graph: ClinicalKnowledgeGraph) -> ClinicalKnowledgeGraph:
        graph.provenance.graph_target = self.settings.target
        graph.json_ld = self.emit_json_ld(graph)
        if self.settings.emit_lpg():
            graph.cypher_queries = self.emit_cypher(graph)
        if self.settings.emit_rdfs():
            try:
                from clinical_gliner_kg.graph.rdf import RdfEmitter

                rdf = RdfEmitter(self.settings.rdfs)
                graph.turtle = rdf.serialize(graph, "turtle")
                graph.rdf_jsonld = rdf.json_ld(graph)
                if self.settings.rdfs.serialization == "rdfxml":
                    graph.rdfxml = rdf.serialize(graph, "xml")
                graph.sparql = rdf.default_queries(graph)
            except RuntimeError:
                graph.turtle = graph.turtle or self.emit_turtle(graph)
        else:
            graph.turtle = self.emit_turtle(graph)
        return graph

    def emit_cypher(self, graph: ClinicalKnowledgeGraph) -> list[str]:
        queries: list[str] = []
        meta = graph.provenance
        safe = _safe_ids(graph)
        pending = self.settings.lpg.emit_pending
        for ent in graph.entities:
            if ent.is_phi or ent.id not in safe:
                continue
            code = ent.terminology.code if ent.terminology else "UNLINKED"
            system = ent.terminology.system if ent.terminology else "NONE"
            version = ent.terminology.version if ent.terminology else ""
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
                + "', e.term_version = '"
                + _esc(version)
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
                + "', e.key = '"
                + _esc(ent.idempotency_key)
                + "'"
            )
        for rel in graph.relations:
            if not _emit_relation(rel, safe, emit_pending=pending):
                continue
            rel_type = "PENDING_" + rel.relation if rel.validation_status == ValidationStatus.NEEDS_REVIEW else rel.relation
            queries.append(
                "MATCH (s {id: '"
                + _esc(rel.subject_id)
                + "'}), (o {id: '"
                + _esc(rel.object_id)
                + "'}) "
                + "MERGE (s)-[r:"
                + rel_type
                + " {key: '"
                + _esc(rel.idempotency_key)
                + "'}]->(o) "
                + "SET r.confidence = "
                + f"{rel.confidence:.3f}"
                + ", r.status = '"
                + rel.validation_status.value
                + "', r.doc_id = '"
                + _esc(meta.document_id)
                + "'"
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
                "clin": "https://ypcc.dev/clinical-gliner-kg/ontology#",
            },
            "@id": f"urn:doc:{graph.document_id}",
            "prov:generatedAtTime": graph.provenance.extracted_at,
            "prov:wasDerivedFrom": graph.document_id,
            "prov:wasGeneratedBy": graph.provenance.extraction_backend,
            "entities": [ent.model_dump() for ent in graph.entities if ent.id in safe],
            "relations": [
                rel.model_dump()
                for rel in graph.relations
                if _emit_relation(rel, safe)
            ],
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
                lines.append(f'  ex:termVersion "{_esc(ent.terminology.version)}" ;')
            lines.append(f'  ex:status "{ent.validation_status.value}" ;')
            lines.append(f"  ex:confidence {ent.confidence:.3f} .")
        for rel in graph.relations:
            if not _emit_relation(rel, safe):
                continue
            lines.append(f"ex:{rel.subject_id} ex:{rel.relation} ex:{rel.object_id} .")
        return "\n".join(lines) + "\n"
