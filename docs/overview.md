# Overview

C-Star is built on a system of **applications** (a model or computation you want to run) and **blueprints** (the set of inputs to a given application to get a reproducible result).

The C-Star Forge application streamlines the creation of ROMS-MARBL domains by automating the generation of all required input files using [ROMS Tools](https://roms-tools.readthedocs.io/en/latest/index.html).
The files include grids, initial conditions, boundary and surface forcing, rivers, and tidal forcing—from a variety of observational and reanalysis datasets.
The result is a reproducible blueprint (and the data files it references) for the ROMS-MARBL application.

## The workflow at a glance


1. **Author a forge blueprint.** An interactive **wizard** (run in Jupyter, or served as
   a standalone [Voilà](https://voila.readthedocs.io/) web app) helps you assemble a
   `ForgeBlueprint` starting from catalog **specs** — model (`ModelSpec`), domain (`DomainSpec/`),
   forcing (`ForcingSpec/`), and output (`OutputSpec/`). You can customize any aspect of your simulation and optionally save the modified specs back to the catalog for re-use. The result is a single YAML file
   that fully describes what to generate. Every value is editable in the wizard, and the
   blueprint records the provenance of each choice.
2. **Process the blueprint.** The **forge application** consumes the forge blueprint:

   ```bash
   cstar blueprint run path/to/forge_blueprint.yaml
   ```

   It downloads/prepares source data, generates all ROMS input files, renders model
   settings, and emits a **ROMS-MARBL blueprint** (`RomsMarblBlueprint`) — a YAML file
   (`B_{name}.yaml`, plus a `settings_B_{name}.yaml` sidecar) capturing the complete
   configuration and file paths of the resulting setup.
3. **Run the simulation.** [C-Star](https://c-star.readthedocs.io) consumes the
   ROMS-MARBL blueprint to build the model and execute the actual ROMS-MARBL simulation.

## Key Features

- **Interactive blueprint wizard**: Assemble, review, and save a `ForgeBlueprint` from
  catalog specs — in a notebook or a code-free web form
- **Automated Input Generation**: Generate all ROMS input files (grid, initial conditions, forcing, boundaries, rivers, tidal forcing) from source datasets
- **Multi-Dataset Support**: Integrates with multiple data sources including:
  - GLORYS (ocean reanalysis)
  - ERA5 (atmospheric reanalysis)
  - UNIFIED_BGC (biogeochemical climatology)
  - SRTM15 (bathymetry)
  - DAI / GLOFAS (river discharge)
  - TPXO (tidal forcing)
- **ROMS-MARBL Blueprint System**: Automatically generates YAML blueprints that document:
  - Complete model specification (repositories, code versions, input configurations)
  - All generated input file paths (both full and partitioned)
  - Domain configuration (grid name, time ranges, boundaries, processor layout)
  - Source data provenance
- **Reproducible Workflows**: Blueprints serve as complete descriptors that enable:
  - Exact reproduction of model configurations
  - Integration with C-Star workflow management
  - Version control and sharing of domain setups
