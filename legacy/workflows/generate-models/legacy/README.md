# Legacy notebooks

The notebooks in this directory (`CStarSpecBuilder-demo.ipynb`,
`CStarSpecEngine-build-one.ipynb`, `CStarSpecEngine-build-all.ipynb`) describe the
pre-`ForgeBlueprint` design — the deleted `CstarSpecBuilder`/`CstarSpecEngine` classes and
their preconfig/postconfig/build/run stage machine. They are kept for historical
reference only; the current workflow (catalog specs + wizard → `ForgeBlueprint` →
`python -m cstar_forge.run` → `ForgeExecutor`) is documented in
`docs/domain-generation-overview.md` and `docs/developer-guide.md`.
