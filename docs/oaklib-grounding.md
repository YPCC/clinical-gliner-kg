# oaklib grounding (local, no API required)

This repo uses **[oaklib](https://incatools.github.io/ontology-access-kit/)** (Ontology Access Kit) to ground extracted spans to ontology CURIEs.

Choose the mode in [`config/pipeline.yaml`](../config/pipeline.yaml) (see [configuration.md](configuration.md)):

```yaml
oaklib:
  mode: local          # local | ols | bioportal
  eager: false
  local:
    adapters:
      - simpleobo:data/ontologies/mini_clinical.obo
```

**You do not need a BioPortal, OLS, or other API key for `mode: local`.** oaklib talks to **ontology files on disk**. Remote adapters exist, but they are optional (`mode: ols` or `mode: bioportal`).

Official documentation (read these first):

- Home: [incatools.github.io/ontology-access-kit](https://incatools.github.io/ontology-access-kit/)
- Introduction (local files vs remote APIs): [Introduction](https://incatools.github.io/ontology-access-kit/introduction.html)
- FAQ, including “Can OAK access local files?”: [FAQ](https://incatools.github.io/ontology-access-kit/faq/general.html)
- SQL / SQLite adapter (`sqlite:` and `sqlite:obo:`): [SQL Database Adapter](https://incatools.github.io/ontology-access-kit/packages/implementations/sqldb.html)
- Basics / selectors: [OAK Basics](https://incatools.github.io/ontology-access-kit/guide/basics.html)
- Text annotation: [CLI `annotate`](https://incatools.github.io/ontology-access-kit/cli.html) (same `annotate_text` API we call)
- Source: [INCATools/ontology-access-kit](https://github.com/INCATools/ontology-access-kit)
- OBO Academy CLI tutorial: [Zenodo 7708963](https://doi.org/10.5281/zenodo.7708963)

## What “local” means

From the OAK FAQ: the main use case is an ontology **serialized in a standard format and stored locally** (OBO, OWL, OBO Graphs, or SQLite). The same Python API works if you later point at OLS or BioPortal.

| Selector | Needs network? | Needs API key? | What you must have |
|---|---|---|---|
| `simpleobo:path/to/file.obo` | No | No | The `.obo` file |
| `pronto:path/to/file.obo` | No | No | The `.obo` file |
| `sqlite:path/to/file.db` | No | No | A Semantic-SQL SQLite file |
| `sqlite:obo:mondo` | **First** download of the Foundry snapshot, then offline | No | Disk cache (`pystow`, usually `~/.data/`) |
| `ols:` / `ols4:` | Yes | Usually no | Network |
| `bioportal:` | Yes | **Yes** (`BIOPORTAL_API_KEY`) | Network + key |
| `gilda:` | Index download | No | High RAM; not default here |

This repo’s default is the bundled mini ontology:

```text
simpleobo:data/ontologies/mini_clinical.obo
```

That adapter is opened at process start. It already grounds `type 2 diabetes` → `MONDO:0005148` with method `oaklib-annotate`.

`sqlite:obo:*` snapshots are **not** downloaded unless you set `OAK_EAGER=1`. They are large (tens to hundreds of MB each) and would stall CI.

## How the linker chooses a code

1. Exact / partial hit in `config/terminology_catalog.json` (RxNorm, SNOMED CT, LOINC slice).
2. Else oaklib `annotate_text`, then `basic_search`, on adapters for that entity label.
3. Else the span stays unlinked; the graph still stores the surface form.

See `src/clinical_gliner_kg/components/oak_grounder.py` and `ontology_linker.py`.

## Python (what we call)

```python
from oaklib import get_adapter

adapter = get_adapter("simpleobo:data/ontologies/mini_clinical.obo")
for ann in adapter.annotate_text("type 2 diabetes mellitus"):
    print(ann.object_id, ann.object_label)
```

Full Mondo / ChEBI after you accept the download:

```bash
export OAK_EAGER=1
export OAK_ADAPTERS=sqlite:obo:mondo,sqlite:obo:chebi
```

```python
from oaklib import get_adapter

mondo = get_adapter("sqlite:obo:mondo")  # downloads once, then local SQLite
chebi = get_adapter("sqlite:obo:chebi")
```

Point at files you already curate (no Foundry fetch):

```bash
export OAK_ADAPTERS=simpleobo:/data/ontologies/mondo.obo,sqlite:/data/ontologies/chebi.db
```

CLI equivalent from OAK docs:

```bash
runoak -i sqlite:obo:mondo annotate "type 2 diabetes mellitus"
runoak -i data/ontologies/mini_clinical.obo search diabetes
```

## Disk and license notes

- **sqlite:obo:** uses [Semantic-SQL](https://github.com/INCATools/semantic-sql) builds. First call is a download into the pystow cache; later calls are local.
- **SNOMED CT** is not an OBO Foundry dump you can wget into this repo. Use your licensed RF2 + an adapter you control, or map via Mondo xrefs.
- **RxNorm / LOINC** likewise stay in the static catalog unless you plug in your own local files.
- Bundled `mini_clinical.obo` is a **tiny teaching slice**, not Mondo.

## Why not BioPortal by default

Remote annotators are convenient and require no local files, but they:

- send clinical spans off-box
- need keys and rate limits
- make CI non-deterministic

For a PHI-aware extraction plane, local files are the correct default. Remote adapters remain available through oaklib when you explicitly select them.
