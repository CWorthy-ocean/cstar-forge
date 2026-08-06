# Legacy (deprecated, unsupported)

Pre-wizard tooling kept for reference. Nothing here is imported by the `cstar_forge`
package, exercised by the test suite, or maintained going forward. The supported
workflow is: wizard → `forge_blueprint.yaml` → `python -m cstar_forge.run` →
ROMS-MARBL blueprint → C-Star (see the top-level README).

- `legacy_notebook/` — the old papermill notebook engine (`nb_engine.py`, the
  `workflow.yaml` runner) and Slurm/dask helpers (`compute.py`). Formerly the
  `cstar_forge.legacy_notebook` subpackage; its `run_notebook`/`save_notebook_copy`
  re-exports were removed from `cstar_forge`.
- `workflows/` — the notebook-driven workflows that engine ran: domain generation
  (`generate-models/`, including the pre-`ForgeBlueprint` CStarSpecBuilder/Engine
  notebooks under `generate-models/legacy/`), `skill-assessment/`, `visualization/`,
  `computing-benchmarks/`, and the `source-data/` helper scripts. Committed papermill
  outputs under `*/outputs/papermill/` are still rendered in the docs as examples.
- `blueprints/` — saved ROMS-MARBL blueprints in the legacy per-machine layout
  (`<machine>/<name>/B_*.yaml` + settings sidecars), formerly bundled inside
  `cstar_forge/catalog/blueprints/legacy/`. Two are included in the docs as format
  examples.
