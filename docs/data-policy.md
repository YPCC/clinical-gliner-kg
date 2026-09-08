# Data policy

This repository **does not ship n2c2, i2b2, or MIMIC notes**. Those corpora require a Data Use Agreement and must not be pushed to GitHub.

Parent index: [YPCC/medical-data](https://github.com/YPCC/medical-data).

| Dataset | Access | Role here |
|---|---|---|
| Bundled synthetic clinical notes | open | default NER / RE / KG demo |
| Bundled synthetic PHI notes | open | default PHI gate benchmark |
| [ASQ-PHI](https://data.mendeley.com/datasets/csz5dzp7nx/1) | open (MIT, synthetic) | extra PHI set |
| [NCBI Disease](https://www.ncbi.nlm.nih.gov/research/bionlp/Data/disease/) | open | literature disease NER |
| [BC5CDR](https://www.ncbi.nlm.nih.gov/research/bionlp/Data/cdr/) | open | chemical / disease NER + CID |
| [BioRED](https://ftp.ncbi.nlm.nih.gov/pub/lu/BC8-BioRED-track/) | open | document-level triples |
| n2c2 / i2b2 | DUA | official portal only |
| MIMIC-III / IV | DUA / PhysioNet | official portal only |

Literature loaders download public files into `data/cache/` (gitignored). See `src/clinical_gliner_kg/data/literature.py`.
