# Submitting cstar-forge to conda-forge

`recipe.yaml` in this directory is prep work for a `conda-forge/staged-recipes`
submission. It is **not submittable yet**. `yaml.safe_load` parsing cleanly and
the recipe looking structurally sane is not the same as rattler-build accepting
it end to end — nobody has run `rattler-build build` against it. Treat it as a
draft to build and iterate on locally before it ever goes into a PR.

## Blocked on

1. **A first cstar-forge release on PyPI.** `recipe.yaml`'s `source.url` and
   `source.sha256` are placeholders (`version: "0.1.0"`, a dummy all-zero
   sha256). There is no real sdist to hash yet. Once `cstar-forge` is
   published to PyPI (see `.github/workflows/pypipublish.yaml`), regenerate
   both fields from the real release — e.g.:

   ```
   pip download --no-binary :all: --no-deps -d /tmp/cstar-forge-sdist cstar-forge==<version>
   sha256sum /tmp/cstar-forge-sdist/cstar_forge-<version>.tar.gz
   ```

   or run `grayskull pypi cstar-forge` to regenerate a fresh recipe skeleton
   and diff it against this one.

2. **A conda-forge feedstock for `cstar-ocean`.** The C-Star package
   (PyPI name `cstar-ocean`, imported as `cstar`) that cstar-forge depends on
   directly does not have a conda-forge feedstock as of writing. A
   conda-forge build of cstar-forge cannot resolve its `run: - cstar-ocean` 
   dependency until that feedstock exists and is published. `roms_tools`
   (roms-tools) is already on conda-forge, so that dependency is not blocking.

## Staged-recipes flow (once unblocked)

1. Fork `conda-forge/staged-recipes`.
2. Create `recipes/cstar-forge/` in the fork and copy this `recipe.yaml` in
   (updated per the "Blocked on" items above).
3. Fill in `extra.recipe-maintainers` with real conda-forge/GitHub usernames
   (currently a `TODO_ADD_GITHUB_USERNAME` placeholder — conda-forge requires
   at least one real maintainer before merge).
4. Locally validate with `rattler-build build --recipe recipes/cstar-forge/recipe.yaml`
   (or the staged-recipes CI, which runs this automatically) before opening
   the PR.
5. Open a PR against `conda-forge/staged-recipes` with the new recipe.
   conda-forge's linting/CI bots will review it; expect at least one round of
   maintainer feedback on dependency pins and metadata.
