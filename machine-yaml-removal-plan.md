# Plan: remove the machine YAMLs (machine_config)

**Status:** draft — do NOT execute yet (other work in flight).
**Goal:** delete `catalog/Machines/*.yaml` and the `MachineConfig` plumbing. Still
resolve the host *name* (`_detect_system`, no YAML) and still print the host +
its paths.

## Why this is safe
- Host name = `_detect_system()` (platform/hostname/env) — no YAML. (`config.py:104`)
- The only *substantive* consumer of `MachineConfig` (SLURM account/queue/pes) is
  `prep_cstar_environment` → `ForgeExecutor.run()`, which **no live CLI route reaches**
  (`cstar forge run`, `python -m cstar_forge.run`, and the C-Star `ForgeApplication`
  route all stop after `configure_build` + blueprint emission).
- The only *live* read is `HostPaths.summary()` printing `account`/`pes_per_node`
  (`host.py:46`), which we drop from the printout.

## Scope note — what must NOT change
`machine_id` as a **path component** in `blueprint_dir_for` / `build_dir_for`
(`domain_catalog.py:574-587`) is the *host/system tag*, not the Machines/ store.
It stays. Only the `Machines/*.yaml` **store** is being removed.

## Tier 1 — core removal (the actual ask)
1. **`config.py`**
   - Delete `MachineConfig` (69-86), `load_machine_config` (288-328),
     `_load_machine_config_from_catalog` (534-556), `_get_machine_config` +
     `_machine_config_cache` (567-583), and the `machine_config` branch of
     `__getattr__` (586-590; keep the `AttributeError` fallback).
   - Delete `DataPaths.machines_yaml` field (66) + its assignment (233, 248) +
     docstring mention (54, 72).
   - `resolve_host` (687-692): drop the `machine_config=` kwarg.
2. **`host.py`** — `HostPaths`: drop the `machine_config` field (40) and the
   account/pes block in `summary()` (45-49). Keep `Host: {system}` + the path lines.
3. **`executor.py`** — remove the now-dead `_get_machine_config` (1031-1033).
   Its only caller is the dead executor-run region (Tier 2).

## Tier 2 — retire the dead executor-run region (DECIDED: full removal)
**Decision (pinned):** fully remove the dead run/prep region. It is already
unreachable from every live route, and running RomsMarbl is not the ForgeExecutor's
responsibility. Do NOT stub it for a hypothetical future in-forge run path — re-add
cleanly if/when that path is actually built. Removing `HostPaths.machine_config`
would otherwise leave `prep_cstar_environment` referencing a gone field.
   - Remove `prep_cstar_environment` (2029-…) and `async def run` (2102-2119).
   - Remove the now-unused `from cstar.applications.roms_marbl.app import RomsMarblRunner`
     (executor.py:26) — bonus: drops a slow/circular-import-prone import.
   - Update the `run()` docstring reference in `forge_blueprint_engine.py:323`.

## Tier 3 — remove the catalog Machines/ store
   - Delete `cstar_forge/catalog/Machines/` (MacOS / NERSC_perlmutter / RCAC_anvil .yaml).
   - `domain_catalog.py`: remove `_scan_machines` (310-318) + call (213),
     `_machines` (202), `machine_names`/`machine_path`/`machine_data`
     (522, 616, 657) and layered variants (1335, 1408, 1424), the `"machine"`
     entries in `_KIND_ATTR`/`_KIND_DISPLAY` (1260, 1269), the `"Machines"` entry
     in the `merge` copy list (459), and the layout docstrings (94, 117…).
   - **`_validate_catalog` (491-504): drop the `_machines` requirement** — otherwise
     every non-default catalog fails validation with Machines/ gone. Keep the
     ModelSpec/ check.

## Tests to update (~5 files)
- `test_config.py`: delete `TestMachineConfig`, `TestLoadMachineConfig`,
  `MachineConfig`/`load_machine_config` imports, and `machines_yaml=` in every
  `DataPaths(...)` construction (54, 65, 79, 97, 608, 637, 668).
- `test_core.py`, `test_forge_blueprint.py`: drop `machine_config=None` kwargs
  (many `HostPaths(...)` sites; 1443, 2102ff, 3133, 3383, …).
- `test_input_data.py:81`: drop `machines_yaml=`.
- `test_domain_catalog_github.py:46-47`: already commented out — leave/remove.

## Docs
- `docs/machine-config.md`: this feature's page — rewrite to reflect removal, or
  delete if nothing else lives there.
- Grep for stray `machines.yaml` mentions in docs/memory after the change.

## Verification
- `pytest tests/ -v` full suite green (report count).
- `ruff check cstar_forge/ && ruff format --check` + `pre-commit run --all-files`.
- Smoke: `cstar forge run <a small blueprint>` still prints the host block
  (`Host: MacOS`, working_dir, source_data_cache) and emits the roms_marbl blueprint.
