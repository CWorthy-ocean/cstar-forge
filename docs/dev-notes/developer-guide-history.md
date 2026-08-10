# Developer-guide history (resolved items log)

Historical record extracted from `docs/developer-guide.md` (2026-08-10) per its
own cleanup TODO: the guide now describes only the current state; the dated
narrative of how the repo got there lives here. See also
`architecture-decomposition-plan.md` and `executor-portability-plan.md` for the
original planning docs.

## The decomposition

`CstarSpecBuilder`/`CstarSpecEngine`/`_core.py` were fully deleted and replaced
by the resolver (`build_forge_blueprint`) → `ForgeBlueprint` →
`process_forge_blueprint` (engine → `ForgeExecutor`) architecture. The
`SpecConfig` class was renamed `ForgeBlueprint`; the output artifact was renamed
from bare "blueprint" to "roms_marbl blueprint" to break the terminology
collision. Pre-2026-07-23, `name`/`description` lived under a now-removed
`identity` sub-model (the v3→v4 before-validator migration flattens old files);
`ensemble_id` was removed as a dead concept (v2→v3 migration reproduces the old
derived name bit-for-bit). On 2026-07-23 `ForgeBlueprint` became a real
`cstar.orchestration.models.Blueprint` subclass, making forge a genuine C-Star
application.

## Resolved follow-up items (from the guide's former §6)

1. **Utility-module relocation (DONE 2026-07-09)**: `namelist_model.py` and
   `util.py` moved into `cstar_forge/forge/`; imports updated everywhere; both
   added to the boundary guard's `_FORGE_APP_MODULES`.
2. **`code.location` in `content_hash` (DONE 2026-07-09)**: `content_hash()`
   scrubs `location` from every code repo before hashing (test:
   `test_content_hash_ignores_code_repo_location`); `_build_code` reads a
   `code.templates_commit:` pin from `model.yaml`, and the bundled
   `cson_roms-marbl_v0.1` ModelSpec pins a real commit SHA.
3. **`refactor` branch merge**: merged into `main` (squash) 2026-08; the
   raw-URL template-fetch path now resolves against the real remote.
4. **Two stale compile-time-settings TODOs in `input_data.py` (REMOVED
   2026-07-09)**: both predated the code that resolved them; the
   boundary-forcing one had no evident target — every boundary-related cppdefs
   flag is a static default or driven by domain-level `open_boundaries`
   (inferred from the template, not confirmed with a ROMS-MARBL domain expert;
   no missing wiring found).
5. **Stale `forge_blueprint.py` docstring (DONE)**: resolved during the
   2026-07-23 application work.
6. **Stale `examples/` artifacts (DONE 2026-08-06)**: `examples/` deleted along
   with dev artifacts in `catalog/blueprints/`; the maintained example is
   `docs/forge-blueprint-example.wio-toy.yaml`.
7. **`domain_catalog_sketch.py` (DONE)**: deleted.
8. **Architecture doc headers (DONE 2026-07-17)**: planning docs' stale
   "proposal"/"executing" status lines now point at the developer guide.

## Item-model unification (former §5 history)

`models.py` and `forge/forge_blueprint.py` once carried two parallel item-model
schemas kept in sync by a "lockstep drift guard" test. Resolved: `models.py`
now imports the item models from `forge.forge_blueprint` (single source). The
old ModelSpec `inputs`/split `templates`+`settings` shape
(`GridInput`/`ForcingInput`/`ModelInputs`/`SettingsStage`/`SettingsSpec`/
`TemplatesSpec`) was consolidated in 2026-07. `OpenBoundaries` was defined
twice until 2026-07-09; both executor modules now import it from
`forge.forge_blueprint`, and `cstar_forge.forge` no longer imports
`cstar_forge.models` at all.

## Docs that referenced the deleted `_core.py` design (former §7, FIXED 2026-07-09)

All seven live MyST pages were fixed in place rather than deleted:
`domain-generation-overview.md` (banner + updated mermaid), the two InputData
pages (~4 lines of drift in 803), `overview.md` (tree updated),
`machine-config.md` (fixed then, found stale again and re-fixed in the
2026-08-10 docs pass), and the two dev-notes planning docs (historical banners).
The full-repo docs freshness audit of 2026-08-10 (four parallel audit agents,
~70 corrections, `catalog.ipynb` dropped) is recorded in that pass's PR.

## Golden-fixture provenance

The settings-level golden (`test_golden_model_settings_test_tiny`) and the
byte-exact `namelist.nml` golden (`TestGoldenNamelist`, added 2026-07-16) are
described in the current guide; their motivating history (deferred byte-golden
decision, UPDATE_GOLDEN workflow design) is in the planning docs above.
