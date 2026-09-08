# Contributing

1. Keep the default test path free of model downloads and API keys.
2. Do not commit n2c2, i2b2, MIMIC, or any other DUA-protected notes.
3. Add open evaluation sources to `data/catalogs/medical_data_index.yaml` rather than vendoring their files.
4. Prefer extending backends behind `resolve_backend()` so `auto` keeps working.
5. Run `pytest -q` and `python examples/run_pipeline.py --backend heuristic` before opening a PR.
6. Architecture, oaklib, and bibliography live in `docs/`. Keep README diagrams in mermaid; do not restore ASCII flowcharts.

