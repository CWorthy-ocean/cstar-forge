# Getting Started

This page takes you from nothing to a running toy simulation on a laptop or
workstation: install, build a small forge blueprint with the wizard, process
it, and hand the result to C-Star to run.

Installing on an HPC system, or setting up a development environment with an
editable checkout? Use the [Installation](installation.md) page instead, then
rejoin this guide at [Register for data access](#register-for-data-access).

## Install

The easiest way to get our entire dependency stack is to install `cstar-forge` and `cstar-ocean-standalone` into a fresh conda (or mamba) environment:

```bash
conda create -n cstar-forge-env -c conda-forge cstar-forge cstar-ocean-standalone
conda activate cstar-forge-env
```

Verify:

```bash
cstar --version
python -c "import cstar_forge; print('cstar_forge OK')"
```

```{note}
`cstar-ocean-standalone` installs its own conda-based compiler and MPI stack; if you are on a HPC or machine with its own bespoke compilers and MPI setup, use the regular `cstar-ocean` package.
```

(register-for-data-access)=
## Register for data access

Forge downloads forcing data from open datasets, two of which need a one-time
free registration — full instructions on the
[Registering with data sources](data-access.md) page. For this walkthrough:

- **GLORYS (Copernicus Marine) is required**: [sign up](data-access.md#data-access-glorys),
  then run `copernicusmarine login` once so Forge can download ocean-state data.
- **TPXO is not needed for this example** — it's required only for domains with
  tidal forcing. When you get there, see the
  [TPXO instructions](data-access.md#data-access-tpxo).

## Build a forge blueprint with the wizard

```bash
cstar forge wizard        # serves the wizard at http://localhost:8866
```

In the wizard: pick a model spec, then pick the **`wio-toy`** domain from the
catalog — a deliberately tiny (20×20×10) Western Indian Ocean domain that
processes in minutes and exists exactly for first runs like this one. Review
the resolved YAML in the Review pane, then **Save** (or **Download**)
`forge_blueprint.yaml`.

```{tip}
In a hurry? A ready-made wio-toy blueprint ships with the package
(`cstar_forge/catalog/blueprints/cson_roms-marbl_v0.1_wio-toy_10procs.forge_blueprint.yaml`)
and in the repo as `docs/forge-blueprint-example.wio-toy.yaml` — you can skip
the wizard entirely and process it directly.
```

## Process the blueprint

```bash
cstar forge run path/to/forge_blueprint.yaml
```

This fetches the source data (GLORYS, ERA5 — expect the first run to spend
most of its time downloading), generates all ROMS input
files, renders the model settings, and emits a **ROMS-MARBL blueprint** under
the blueprint's `working_dir` (for wio-toy:
`~/cstar-forge-run/cson_roms-marbl_v0.1_wio-toy_10procs/`). The final line of
output tells you exactly what to do next:

```text
Blueprint: ~/cstar-forge-run/.../roms_marbl_blueprint.yaml
Run it with:  cstar blueprint run <path>
```

The full executor option set (stage selection, `--clobber`, dask tuning,
`--only-inputs`, verbosity) is documented in `cstar forge run --help`. The
equivalent `python -m cstar_forge.run` module CLI remains available as a
fallback if the `cstar forge` sub-app isn't registered in your environment.

## Run the simulation

```bash
cstar blueprint run <path-to-roms_marbl_blueprint.yaml>
```

This is a different command than the previous step. The `application` field
inside each blueprint YAML is what selects which application processes it.
The **forge blueprint** (`application: forge`) used the dedicated
`cstar forge run` entry point above because forge is an out-of-tree C-Star
application (its `cstar.cli` sub-app also exposes forge-specific power-user
options that the generic runner doesn't). This generated **ROMS-MARBL
blueprint** (`application: roms_marbl`), with all of the inputs needed to
execute the simulation, is a built-in C-Star application that C-Star's
generic `cstar blueprint run` command already knows how to dispatch to
directly, with no extra setup.

C-Star fetches and compiles the model code (using the toolchain installed
above) and executes the simulation; outputs land under the same working
directory. See the [C-Star documentation](https://c-star.readthedocs.io) for more details on run management,
workplans, and analysis.

## Next steps

- Browse the bundled **domain catalog** in the wizard or customize a domain's grid parameters.
- Moving to a cluster? The [Installation](installation.md) page covers HPC
  installs (with the toolchain coming from environment modules instead of
  conda) and reproducible locked environments.
