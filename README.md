# C-Star Forge has moved into C-Star

> **This repository is retired.** C-Star Forge -- the wizard, resolver, catalog,
> executor and `cstar forge` CLI for generating regional ROMS-MARBL domains --
> ships inside [`cstar-ocean`](https://github.com/CWorthy-ocean/C-Star) from
> version **0.15.0**. Development, issues and pull requests continue there.
> Documentation: <https://c-star.readthedocs.io/en/latest/forge/index.html>.

<p align="center"><img src="docs/assets/csforge.png" alt="C-Star Forge logo" width="300"></p>

## Installing

There is nothing separate to install any more:

```bash
conda install -c conda-forge cstar-ocean   # or: pip install cstar-ocean
cstar forge --help
```

The `cstar-forge` package on PyPI and conda-forge (0.9.x) is a **compatibility
shim** that depends on `cstar-ocean >= 0.15.0` and forwards the old
`cstar_forge.*` import paths to their new homes with a `DeprecationWarning`.
Nothing in it does any work. Once your imports are updated,
`pip uninstall cstar-forge` (or `conda remove cstar-forge`).

## What changed for users

| Before (cstar-forge 0.8.x) | Now (cstar-ocean 0.15+) |
|---|---|
| `cstar forge run`, `cstar forge wizard`, `cstar forge show-paths`, `cstar forge copy-notebook` | unchanged, built into `cstar` |
| `cstar forge register-kernel` | `cstar env register-kernel` |
| `python -m cstar_forge.run <blueprint>` | `cstar forge run <blueprint>` |
| `CSTAR_FORGE_CATALOG` | `CSTAR_CATALOG` |
| writable catalog at `~/cstar-forge-data/catalog` | `~/cstar/catalog` (a catalog at the old location is not read; forge logs a hint) |
| `forge_version` stamp in forge blueprints | `cstar_version` (old files still load) |

Source-data cache, working-directory relocation onto HPC scratch, and every
generated file location are unchanged.

## What changed for Python imports

| Before | Now |
|---|---|
| `cstar_forge.forge.forge_blueprint` | `cstar.applications.forge.blueprint` |
| `cstar_forge.forge.forge_blueprint_engine` | `cstar.applications.forge.engine` |
| `cstar_forge.forge.executor`, `.settings`, `.input_data`, `.source_datasets`, `.namelist_model`, ... | `cstar.applications.forge.<same name>` |
| `cstar_forge.forge_blueprint_resolve` | `cstar.applications.forge.resolve` |
| `cstar_forge.models`, `cstar_forge.config` | `cstar.applications.forge.models`, `.config` |
| `cstar_forge.run` | `cstar.applications.forge.runtime` |
| `cstar_forge.domain_catalog` | `cstar.catalog.domain_catalog` |
| `cstar_forge.forge_blueprint_wizard`, `cstar_forge.ui.*` | `cstar.wizard.wizard`, `cstar.wizard.ui.*` |
| `cstar_forge.cli` | `cstar.cli.forge` |
| `cstar_forge.register_kernel` | `cstar.cli.environment.register_kernel` |

The full table is `cstar_forge.MODULE_ALIASES` in this package.

## History

The complete cstar-forge commit history was imported into C-Star
([C-Star #699](https://github.com/CWorthy-ocean/C-Star/pull/699)), so `git blame`
and `git log --follow` on the relocated files continue to work there. Release
notes for the standalone package (0.1.0 through 0.8.2) are kept in
[`docs/releases.md`](docs/releases.md) and under *Releases* in the C-Star docs.
