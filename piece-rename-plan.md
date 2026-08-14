# "Pieces" → "specs" rename plan

Rename the collective concept currently called **"Pieces"** (the composable
`ModelSpec` / `DomainSpec` / `ForcingSpec` / `OutputSpec` selections that compose
into a `ForgeBlueprint`) to **"specs"**.

**Decision:** `spec` / `Spec`. Chosen over `component` (adds a second noun beside
the surviving `*Spec` suffix) and `template` (collides with `templates/` Jinja).
The piece *types* are already `*Spec`, so this reuses existing vocabulary rather
than introducing a new word — `SpecRef → ModelSpec` is self-documenting.

## Key facts (why this is low-risk)

- The piece types are **already** `*Spec` (`ModelSpec`, `DomainSpec`,
  `ForcingSpec`, `OutputSpec`) — class names and `cstar_forge/catalog/<X>Spec/`
  dir names. These **stay exactly as-is**; only the *reference* type (`PieceRef`)
  and the collective vocabulary ("Pieces") change.
- `PieceRef` serializes to `{name, origin, modified}` — the class name **never
  appears in saved blueprint YAML** (verified: `grep -rl Piece
  cstar_forge/catalog/blueprints/` → 0 hits). Renaming the class is a pure code
  change, **no on-disk schema migration**.
- The serialized field names under `composition` (`model/domain/forcing/output`)
  are **not** renamed — they stay. Blueprints on disk are untouched.
- `.claude/worktrees/cdr-output-enable/` is a separate branch's worktree (full
  mirror) — **do not edit**; its copies appear in greps, ignore them.

## Scope (main tree only)

### 1. Type rename: `PieceRef` → `SpecRef`  (42 refs)
- `cstar_forge/forge/forge_blueprint.py:898` — `class PieceRef` → `class SpecRef`
  + docstring ("one composable piece …" → "one composable spec …").
- `cstar_forge/forge/forge_blueprint.py:919-925` — the four
  `Field(default_factory=PieceRef)` on `Composition` → `SpecRef`.
- `cstar_forge/forge_blueprint_wizard.py:52` — import; construction sites
  (~3076–3085).
- `cstar_forge/forge_blueprint_resolve.py:50,76,864-871` — imports + construction.
- All remaining `PieceRef(` call sites and type annotations.

### 2. UI label + tests
- `forge_blueprint_wizard.py:4941` — `"Pieces"` accordion/section title →
  `"Specs"`.
- `forge_blueprint_wizard.py:5028-5030` — `"Save modified pieces to catalog"`
  button + help text → `"Save modified specs to catalog"`.
- `tests/test_forge_blueprint_wizard.py:288-293` —
  `test_pieces_section_has_forcing_and_output_dropdowns` asserts on
  `<b>Pieces</b>`; rename test → `test_specs_section_...` + assertion string to
  `<b>Specs</b>`.

### 3. Internal method / variable / dispatch-string names (wizard)
- `_domain_piece_data` → `_domain_spec_data`
- `_verify_piece_roundtrip` → `_verify_spec_roundtrip`
- `_piece_save_row` → `_spec_save_row`
- local dispatch var `piece` (in `piece == "output"/"model"/"forcing"/"domain"`)
  → `spec`; the string *values* stay unchanged.
- The `# … piece …` comments in `forge_blueprint_wizard.py` (63 hits, mostly
  comments), `forge_blueprint_resolve.py` (11), `forge/forge_blueprint.py` (13)
  → "spec".
- Watch for existing generic uses of the word "spec" so renamed locals don't
  shadow anything — none expected, but grep after.

### 4. Docs (prose only)
- `docs/architecture-details.md` (×4: "catalog pieces", the diagram label
  `catalog pieces ─┐`) → "catalog specs".
- `docs/domain-generation-overview.md` (×2) — flagged stale in CLAUDE.md; update
  for consistency or leave with its other staleness.
- `docs/getting-started.md:66` (×1).
- Catalog YAML comments: `catalog/OutputSpec/standard/Output.yaml:1`,
  `catalog/ModelSpec/cson_roms-marbl_v0.1/model.yaml:40`.

### 5. Planning docs (your own)
- `docs/catalog-plan.md` — lines 21, 25, 32, 116, 161-162: "pieces" / `PieceRef`
  → "specs" / `SpecRef`, to keep the plan of record coherent with the new name.
- Delete this file (`piece-rename-plan.md`) after the rename lands.

### Not in scope (leave alone)
- `.readthedocs.yaml:20` "pieces" — unrelated (URL/env-var fragments).
- The 14 generic `component` uses — unrelated; not touched by a `spec` rename.

## Execution order

1. (Done in planning) Confirmed no on-disk hit: `grep -rl Piece
   cstar_forge/catalog/blueprints/` → 0.
2. Rename `PieceRef` → `SpecRef` (class + all refs). Import-sort via ruff.
3. Rename wizard internals (methods, local `piece` var, dispatch).
4. Update UI strings + the matching test name/assertion.
5. Update docs + catalog YAML comments + `docs/catalog-plan.md`.
6. `ruff check cstar_forge/ --fix && ruff format cstar_forge/`.
7. Full suite: `pytest tests/ -v` — report pass count (baseline is the current
   green count; expect no behavior change).
8. `pre-commit run --all-files`.

## Naming decision notes (for the record)

- **`spec` (chosen):** the pieces already are `*Spec`; `SpecRef → ModelSpec` is
  self-documenting; matches the team's informal word; zero new vocabulary.
  Mild caveats: generic overload; `SpecRef` sits near the retired `SpecConfig`
  name — judged not enough to outweigh the consistency win.
- **`component` (rejected):** pairs with `Composition`/"compose" but introduces a
  second noun alongside the surviving `*Spec` suffix.
- **`template` (rejected):** collides with `templates/` (cppdefs/namelist Jinja).
