"""RDFS knowledge graph via rdflib + PyLD (JSON-LD). SPARQL against the in-memory graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clinical_gliner_kg.models import ClinicalEntity, ClinicalKnowledgeGraph, ClinicalRelation, ValidationStatus
from clinical_gliner_kg.settings import REPO_ROOT, RdfsSettings

CLIN = "https://ypcc.dev/clinical-gliner-kg/ontology#"
PROV = "http://www.w3.org/ns/prov#"
XSD = "http://www.w3.org/2001/XMLSchema#"

REL_IRI = {
    "HAS_CONDITION": "hasCondition",
    "TAKES": "takes",
    "TREATS": "treats",
    "HAS_VALUE": "hasValue",
    "INDICATES": "indicates",
    "PERFORMED": "performed",
    "HAS_ANATOMICAL_SITE": "hasAnatomicalSite",
    "CID": "chemicalInducesDisease",
}

_DROP = {ValidationStatus.REJECTED, ValidationStatus.LLM_REJECTED}

JSONLD_CONTEXT = {
    "clin": CLIN,
    "prov": PROV,
    "xsd": XSD,
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "prefLabel": "clin:prefLabel",
    "code": "clin:code",
    "status": "clin:status",
    "confidence": "clin:confidence",
    "treats": {"@id": "clin:treats", "@type": "@id"},
    "hasCondition": {"@id": "clin:hasCondition", "@type": "@id"},
    "takes": {"@id": "clin:takes", "@type": "@id"},
    "hasValue": {"@id": "clin:hasValue", "@type": "@id"},
    "indicates": {"@id": "clin:indicates", "@type": "@id"},
}


def _rdflib():
    try:
        from rdflib import Graph, Literal, Namespace, URIRef
        from rdflib.namespace import RDF, RDFS, XSD as XSD_NS, PROV

        return Graph, Literal, Namespace, URIRef, RDF, RDFS, XSD_NS, PROV
    except ImportError as exc:
        raise RuntimeError("rdflib is required for RDFS/SPARQL. pip install 'clinical-gliner-kg[graph]'") from exc


class RdfEmitter:
    def __init__(self, settings: RdfsSettings | None = None) -> None:
        self.settings = settings or RdfsSettings()

    def build(self, kg: ClinicalKnowledgeGraph):
        Graph, Literal, Namespace, URIRef, RDF, RDFS, XSD_NS, PROV = _rdflib()
        g = Graph()
        clin = Namespace(CLIN)
        base = self.settings.base_iri.rstrip("/") + "/"
        g.bind("clin", clin)
        g.bind("prov", PROV)
        g.bind("rdfs", RDFS)

        onto = Path(self.settings.ontology)
        if not onto.is_absolute():
            onto = REPO_ROOT / onto
        if onto.exists():
            g.parse(onto, format="turtle")

        doc = URIRef(f"{base}doc/{kg.document_id}")
        g.add((doc, RDF.type, clin.ClinicalDocument))
        g.add((doc, PROV.generatedAtTime, Literal(kg.provenance.extracted_at)))
        g.add((doc, PROV.wasGeneratedBy, Literal(kg.provenance.extraction_backend)))

        safe = {ent.id for ent in kg.entities if not ent.is_phi}
        nodes: dict[str, Any] = {}
        for ent in kg.entities:
            if ent.id not in safe:
                continue
            node = URIRef(f"{base}ent/{ent.id}")
            nodes[ent.id] = node
            klass = clin[ent.label] if ent.label else clin.ClinicalEntity
            g.add((node, RDF.type, klass))
            g.add((node, clin.prefLabel, Literal(ent.text)))
            g.add((node, clin.status, Literal(ent.validation_status.value)))
            g.add((node, clin.confidence, Literal(ent.confidence)))
            g.add((node, clin.linkingConfidence, Literal(ent.linking_confidence)))
            g.add((node, clin.startChar, Literal(ent.start_char)))
            g.add((node, clin.endChar, Literal(ent.end_char)))
            g.add((node, clin.evidenceSpan, Literal(ent.text)))
            g.add((node, PROV.wasDerivedFrom, doc))
            if ent.idempotency_key:
                g.add((node, clin.idempotencyKey, Literal(ent.idempotency_key)))
            if ent.terminology:
                g.add((node, clin.code, Literal(f"{ent.terminology.system}:{ent.terminology.code}")))
                g.add((node, clin.terminologySystem, Literal(ent.terminology.system)))
                g.add((node, clin.terminologyVersion, Literal(ent.terminology.version)))
            for event in ent.history:
                g.add((node, clin.decisionComment, Literal(f"{event.actor}:{event.decision}:{event.comment}")))

        for rel in kg.relations:
            if rel.validation_status in _DROP:
                continue
            if rel.subject_id not in nodes or rel.object_id not in nodes:
                continue
            pred_name = REL_IRI.get(rel.relation, rel.relation.lower())
            pred = clin[pred_name]
            g.add((nodes[rel.subject_id], pred, nodes[rel.object_id]))
            if not self.settings.include_assertions:
                continue
            aid = rel.idempotency_key or f"{rel.subject_id}_{rel.relation}_{rel.object_id}"
            assertion = URIRef(f"{base}assert/{aid}")
            g.add((assertion, RDF.type, clin.Assertion))
            g.add((assertion, clin.subject, nodes[rel.subject_id]))
            g.add((assertion, clin.predicate, pred))
            g.add((assertion, clin.object, nodes[rel.object_id]))
            g.add((assertion, clin.status, Literal(rel.validation_status.value)))
            g.add((assertion, clin.confidence, Literal(rel.confidence)))
            g.add((assertion, PROV.wasDerivedFrom, doc))
            g.add((assertion, PROV.wasGeneratedBy, Literal(rel.source_model)))
            if rel.validation_comment:
                g.add((assertion, clin.decisionComment, Literal(rel.validation_comment)))
            if rel.adjudication_model:
                g.add((assertion, PROV.wasAssociatedWith, Literal(rel.adjudication_model)))
            if rel.idempotency_key:
                g.add((assertion, clin.idempotencyKey, Literal(rel.idempotency_key)))
            for event in rel.history:
                g.add((assertion, clin.decisionComment, Literal(f"{event.at}|{event.actor}|{event.decision}|{event.comment}")))

        if self.settings.infer == "rdfs":
            try:
                import owlrl

                owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)
            except Exception:
                pass
        return g

    def serialize(self, kg: ClinicalKnowledgeGraph, fmt: str | None = None) -> str:
        g = self.build(kg)
        fmt = fmt or self.settings.serialization
        mapping = {"turtle": "turtle", "ttl": "turtle", "ntriples": "nt", "rdfxml": "xml", "xml": "xml", "jsonld": "json-ld"}
        return g.serialize(format=mapping.get(fmt, "turtle"))

    def json_ld(self, kg: ClinicalKnowledgeGraph) -> dict[str, Any]:
        raw = self.serialize(kg, "jsonld")
        import json

        data = json.loads(raw)
        try:
            from pyld import jsonld

            return jsonld.compact(data, JSONLD_CONTEXT)
        except Exception:
            return data if isinstance(data, dict) else {"@graph": data}

    def query(self, kg: ClinicalKnowledgeGraph, sparql: str) -> list[dict[str, str]]:
        g = self.build(kg)
        rows: list[dict[str, str]] = []
        for row in g.query(sparql):
            rows.append({str(var): str(row[var]) if row[var] is not None else "" for var in row.labels})
        return rows

    def default_queries(self, kg: ClinicalKnowledgeGraph) -> dict[str, list[dict[str, str]]]:
        treats = """
PREFIX clin: <https://ypcc.dev/clinical-gliner-kg/ontology#>
SELECT ?medLabel ?condLabel WHERE {
  ?med clin:treats ?cond .
  ?med clin:prefLabel ?medLabel .
  ?cond clin:prefLabel ?condLabel .
}
"""
        unlinked = """
PREFIX clin: <https://ypcc.dev/clinical-gliner-kg/ontology#>
SELECT ?label WHERE {
  ?ent clin:prefLabel ?label ;
       clin:status "UNLINKED" .
}
"""
        return {
            "treats": self.query(kg, treats),
            "unlinked": self.query(kg, unlinked),
        }
