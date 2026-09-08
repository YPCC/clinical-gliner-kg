# Bibliography

Works and software that this extraction plane is built on. Canonical BibTeX: [`references.bib`](references.bib).

## Extraction models

1. Zaratiana U, Tomeh N, Holat P, Charnois T. **GLiNER: Generalist Model for Named Entity Recognition using Bidirectional Transformer.** In: *NAACL 2024*. p. 5364–5376. [doi:10.18653/v1/2024.naacl-long.300](https://doi.org/10.18653/v1/2024.naacl-long.300) · [ACL Anthology](https://aclanthology.org/2024.naacl-long.300/)
2. Stepanov I, Shtopko M. **GLiNER multi-task: Generalist Lightweight Model for Various Information Extraction Tasks.** arXiv:2406.12925. 2024. [https://arxiv.org/abs/2406.12925](https://arxiv.org/abs/2406.12925)
3. Fastino. **GLiNER 2 / GLiNER 2.5** (boundary decoder, JointIE, long context). [github.com/fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2) · [Hugging Face demo](https://huggingface.co/spaces/fastino/gliner25-long-context)
4. Zaratiana U et al. **GLiNER** (reference implementation). [github.com/urchade/GLiNER](https://github.com/urchade/GLiNER)

## Orchestration

5. Honnibal M, Montani I, Van Landeghem S, Boyd A. **spaCy: Industrial-strength Natural Language Processing in Python.** [spacy.io](https://spacy.io)
6. Explosion. **spaCy-LLM** (`NER.v3` and related tasks). [github.com/explosion/spacy-llm](https://github.com/explosion/spacy-llm)
7. TheirStory. **gliner-spacy** spaCy factory. [github.com/theirstory/gliner-spacy](https://github.com/theirstory/gliner-spacy)

## Ontology access (why oaklib)

oaklib is the local grounding layer. **No API key is required** when you point it at OBO or SQLite files on disk. Remote OLS / BioPortal adapters are optional.

8. INCATools. **Ontology Access Kit (oaklib).** Documentation: [incatools.github.io/ontology-access-kit](https://incatools.github.io/ontology-access-kit/) · [Introduction](https://incatools.github.io/ontology-access-kit/introduction.html) · [FAQ (local files)](https://incatools.github.io/ontology-access-kit/faq/general.html) · [SQLite adapter](https://incatools.github.io/ontology-access-kit/packages/implementations/sqldb.html) · [GitHub](https://github.com/INCATools/ontology-access-kit)
9. OBO Academy. **Using the OAK command line.** Zenodo. [doi:10.5281/zenodo.7708963](https://doi.org/10.5281/zenodo.7708963)
10. INCATools. **Semantic-SQL** (SQLite builds consumed by `sqlite:obo:`). [github.com/INCATools/semantic-sql](https://github.com/INCATools/semantic-sql)
11. Caufield JH, et al. **Structured data extraction from unstructured text using generative AI and ontologies (OntoGPT / SPIRES).** (oaklib used for grounding). See [monarch-initiative/ontogpt](https://github.com/monarch-initiative/ontogpt)

How we use it in this repo: [oaklib-grounding.md](oaklib-grounding.md).

## Terminologies

12. Donnelly K. **SNOMED-CT: The advanced terminology and coding system for eHealth.** *Stud Health Technol Inform.* 2006.
13. Bodenreider O. **The Unified Medical Language System (UMLS): integrating biomedical terminology.** *Nucleic Acids Res.* 2004;32(Database issue):D267–D270. [doi:10.1093/nar/gkh061](https://doi.org/10.1093/nar/gkh061)
14. NLM. **RxNorm.** [nlm.nih.gov/research/umls/rxnorm](https://www.nlm.nih.gov/research/umls/rxnorm/)
15. McDonald CJ, et al. **LOINC, a universal standard for identifying laboratory observations.** *Clin Chem.* 2003;49(4):624–633. [doi:10.1373/49.4.624](https://doi.org/10.1373/49.4.624)
16. Vasilevsky NA, et al. **Mondo Disease Ontology.** [mondo.monarchinitiative.org](https://mondo.monarchinitiative.org/)
17. Hastings J, et al. **ChEBI in 2016.** *Nucleic Acids Res.* 2016;44(D1):D1214–D1219. [doi:10.1093/nar/gkv1031](https://doi.org/10.1093/nar/gkv1031)
18. Lipscomb CE. **Medical Subject Headings (MeSH).** *Bull Med Libr Assoc.* 2000;88(3):265–266.

## Evaluation corpora

19. Doğan RI, Leaman R, Lu Z. **NCBI disease corpus: a resource for disease name recognition and concept normalization.** *J Biomed Inform.* 2014;47:1–10. [doi:10.1016/j.jbi.2013.12.006](https://doi.org/10.1016/j.jbi.2013.12.006) · PMID 24393765
20. Li J, Sun Y, Johnson RJ, et al. **BioCreative V CDR task corpus: a resource for chemical disease relation extraction.** *Database.* 2016;2016:baw068. [doi:10.1093/database/baw068](https://doi.org/10.1093/database/baw068) · PMID 27161011
21. Luo L, et al. **BioRED: a rich biomedical relation extraction dataset.** *Brief Bioinform.* 2022. [doi:10.1093/bib/bbac282](https://doi.org/10.1093/bib/bbac282)
22. Fries JA, et al. **BigBIO: a framework for biomedical NLP.** *NeurIPS Datasets and Benchmarks.* 2022. [arxiv.org/abs/2206.15076](https://arxiv.org/abs/2206.15076)

## Knowledge graphs and web semantics

23. Neo4j. **Cypher query language.** [neo4j.com/docs/cypher-manual](https://neo4j.com/docs/cypher-manual/current/)
24. W3C. **JSON-LD 1.1.** [w3.org/TR/json-ld11](https://www.w3.org/TR/json-ld11/)
25. W3C. **RDF 1.1 Turtle.** [w3.org/TR/turtle](https://www.w3.org/TR/turtle/)
26. RDFLib. [rdflib.readthedocs.io](https://rdflib.readthedocs.io/)

## Policy / safety context (not a compliance claim)

27. U.S. HHS. **HIPAA Privacy Rule — Protected Health Information.** [hhs.gov/hipaa](https://www.hhs.gov/hipaa/index.html)
28. Stubbs A, Kotfila C, Uzuner Ö. **Automated systems for the de-identification of longitudinal clinical narratives (2014 i2b2/UTHealth).** *J Biomed Inform.* 2015;58 Suppl:S11–S19.

## Dataset catalog

29. Parte Y. **YPCC/medical-data** — open vs DUA biomedical NLP corpora. [github.com/YPCC/medical-data](https://github.com/YPCC/medical-data)
