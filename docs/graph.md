# LPG (Cypher) vs RDFS (SPARQL)

`graph.target` in [`config/pipeline.yaml`](../config/pipeline.yaml) chooses what `process_document` emits.

| `graph.target` | Artifact | Query language |
|---|---|---|
| `lpg` | Neo4j Cypher (`kg.cypher_queries`) | Cypher |
| `rdfs` | rdflib graph → Turtle / JSON-LD / RDF/XML | SPARQL |
| `both` (default) | both | both |

Aliases: `cypher`/`neo4j` → `lpg`; `rdf`/`sparql`/`jsonld` → `rdfs`.

```yaml
graph:
  target: both
  lpg:
    dialect: cypher
    emit_pending: true
  rdfs:
    ontology: data/ontologies/clinical.rdfs.ttl
    serialization: turtle
    infer: none          # rdfs requires owlrl
    base_iri: https://ypcc.dev/clinical-gliner-kg/
    include_assertions: true
  store_path: outputs/kg/assertions.jsonl
```

```bash
export GRAPH_TARGET=rdfs
clinical-gliner --format rdfs --backend heuristic
python examples/run_kg_demo.py --format lpg --outdir outputs/kg
python examples/run_stream_jsonl.py --store outputs/kg/assertions.jsonl
```

## Libraries

- **[rdflib](https://rdflib.readthedocs.io/)** — RDF graph, Turtle/N-Triples/RDF/XML, SPARQL 1.1
- **[PyLD](https://github.com/digitalbazaar/pyld)** — JSON-LD 1.1 compact/expand (the JSON-LD companion people often mean by “ldpy”; the old PyPI `ldpy` is an unmaintained LDP client and is **not** used)
- Optional **owlrl** — RDFS closure when `graph.rdfs.infer: rdfs`

```bash
pip install -e ".[graph]"    # rdflib + PyLD
```

## RDFS schema

[`data/ontologies/clinical.rdfs.ttl`](../data/ontologies/clinical.rdfs.ttl) declares classes (`clin:Medication rdfs:subClassOf clin:ClinicalEntity`) and properties with **RDFS domain/range** (`clin:treats` domain Medication, range Condition). That is schema, not OWL DL.

Every emitted edge is also an n-ary `clin:Assertion` with PROV (`prov:wasDerivedFrom`, `prov:wasGeneratedBy`), confidence, terminology version, idempotency key, and decision-history comments.

## SPARQL example

```sparql
PREFIX clin: <https://ypcc.dev/clinical-gliner-kg/ontology#>
SELECT ?medLabel ?condLabel WHERE {
  ?med clin:treats ?cond .
  ?med clin:prefLabel ?medLabel .
  ?cond clin:prefLabel ?condLabel .
}
```

`kg.sparql["treats"]` is that query, already run.

## Event envelope + JSONL store

`EventEnvelope` is the unit of work. `JsonlGraphStore` upserts by `idempotency_key` (hash of document + spans + relation). Re-processing the same `document_id` retracts keys that disappeared. This is the disk stand-in for Kafka/Neo4j — not a streaming runtime yet.
