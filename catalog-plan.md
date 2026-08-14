# Catalog: short-term fix and long-term architecture

*2026-08-14 — exploration/planning doc. Nothing here is implemented; the short-term work should land after the `user-provided-netcdfs` branch merges.*

---

## 1. Confirmed current state (main @ c36ed09f)

The mental model in the prompt is correct. Details that matter for the design:

**Location & resolution.** The packaged catalog is `cstar_forge/catalog/`, resolved as
`Path(__file__).parent / "catalog"` (`domain_catalog.py:19`), so a conda/pip install puts it in
`site-packages/cstar_forge/catalog/`. A module-level singleton `default_catalog = DomainCatalog()`
is constructed **at import time** (`domain_catalog.py:1127`; a second eager instance in the
deprecated `catalog.py:53` shim). Users can point elsewhere only via the Python API
(`DomainCatalog(catalog_root=...)`) or the wizard's Catalog text box — there is **no env var and
no CLI flag**. `cstar_forge/cli.py` exposes only `run` and `wizard`.

**The site-packages write problem is real and threefold:**
1. Wizard default blueprint save path: `_default_blueprint_path()` (`forge_blueprint_wizard.py:2337-2352`)
   returns `<catalog>/blueprints/<name>.forge_blueprint.yaml` whenever the catalog is local —
   i.e. inside site-packages by default.
2. Workplans: `_workplan_dest()` (`:3977-3989`) → `<catalog>/workplans/`.
3. "Save modified pieces to catalog": all four writers (`register_output`, `register_model_from_settings`,
   `register_domain_from_dict`, `register_forcing`, wired at wizard `:3673-3870`) write directly into
   `site-packages/cstar_forge/catalog/{OutputSpec,ModelSpec,DomainSpec,ForcingSpec}/<name>/`.
   None of them guard on catalog type (unlike `_default_blueprint_path`, which at least falls back
   to CWD for remote catalogs).

**Half-built pieces we can reuse:**
- `config.paths.catalog` already defaults to `~/cstar-forge-data/catalog` (`config.py:204-211`,
  from PR #100 "Move catalog path to user directory") and `config.with_catalog()` exists — but
  **nothing downstream reads it**. It's a vestigial hook, i.e. the user-dir decision was already
  half-made once.
- `DomainCatalog(catalog_root=X, initialize_catalog_from="local")` (`domain_catalog.py:358-415`)
  already copies the packaged spec dirs into a new catalog root — a working "seed a user catalog"
  primitive.
- Read-only **remote catalogs over fsspec** (GitHub org/repo/branch/path, or plain http) already
  work (`domain_catalog.py:102-150`), with `GITHUB_TOKEN` support. There is no git integration
  (no clone/commit/push) — remote is read-only.

**Identity & relationships today:** catalog entries have **no id, version, or hash** — the
directory name is the entire identity. Cross-references are bare name strings
(`Domain.yaml: model_name`, unvalidated) and the blueprint's `composition` block
(`PieceRef {name, origin, modified}` + sparse `overrides`), which is provenance-only and excluded
from `content_hash`. Blueprint→(model, grid) attribution in `roms_marbl_blueprint_df` is recovered
by **filename regex convention** (`domain_catalog.py:1038-1055`). Discovery is pure directory
scanning; no index file.

**Crucial invariant that makes relocation safe:** blueprints snapshot resolved values
(DESIGN-RATIONALE rule 2, "snapshot, don't reference"), and the executor never touches the catalog
(enforced by `tests/test_forge_app_boundary.py`). Moving the catalog cannot break existing
blueprints or runs.

**Known rot to fix while we're in here** (found during this survey):
- `_scan_roms_marbl_blueprints` expects the legacy nested `blueprints/<machine>/<name>/B_*.yaml`
  layout, but the shipped catalog holds flat `*.forge_blueprint.yaml` files → the bundled
  blueprints are invisible (`roms_marbl_blueprint_names == []`). Two different artifact kinds
  (authored forge blueprints vs emitted roms_marbl blueprints) share `blueprints/` with no scanner
  for the former.
- Import-time filesystem scan (twice) on `import cstar_forge`.
- For GitHub-backed catalogs, the four `register_*` writers would silently write under the process
  CWD (repo-relative `catalog_root` + bare `Path.mkdir/open`) instead of raising.
- The packaged catalog ships only implicitly (setuptools_scm file-finder + default
  `include-package-data`; the declared package-data glob is non-recursive and wouldn't match it).
- Docs (`reference-domains.md` etc.) `{include}` bundled catalog files directly — the package must
  keep *some* bundled catalog for docs/tests/demos regardless of where user data lives.

## 2. Impact of the `user-provided-netcdfs` branch (unmerged)

- Attached netCDFs (grid/river/CDR) are referenced by **absolute host path + content hash**
  (`UserProvidedFile{location, content_hash}`); nothing is written into the catalog, and the
  branch deliberately bypasses the existing `add_asset_to_domain` catalog-asset mechanism.
  **Catalog relocation therefore doesn't interact with this branch at all.** The fragility it does
  introduce is *transport* (blueprints with attached files aren't self-contained across machines) —
  a future catalog-assets story could fix that, see §4.5.
- `FORGE_BLUEPRINT_VERSION` 5→6, no-op migration.
- One design lesson that matters for the long-term plan: `content_hash()` hashes
  `model_dump(mode="json")` **without `exclude_none`**, so every additive optional field churns the
  stored hash of every shipped blueprint (all three catalog blueprints' hashes changed on the
  branch for this reason alone). If content hashes are ever used as **join keys** for
  relationship/output tracking (§4), this instability must be fixed first (canonicalize by
  dropping `None` leaves before hashing, or introduce stable creation-time IDs).
- Housekeeping before merge: the branch commits an orphan 57 KB
  `cstar_forge/forge_user_files/wio-toy-simple_grid.nc` inside the package tree (unreferenced,
  wizard-run residue) — remove it.

## 3. Requirements recap

Short-term: user-created blueprints/specs must land somewhere durable and findable, surviving
package upgrades and env rebuilds, while the shipped examples remain browsable.

Long-term:
- R1. Per-user "scratch" catalog for personal specs/blueprints.
- R2. Contribution of selected items to a shared/group or source catalog (collaboration).
- R3. Relationship queries in both directions (blueprints ⇄ modelspec/domainspec).
- R4. Downstream C-Star processes report back: given a domainspec, list all roms_marbl *outputs*.
- R5. HPC-friendly: no long-running database service; scientist-friendly: git > DB admin.

## 4. Long-term architecture

### 4.1 The core recommendation: files-in-git stay canonical; a database becomes a *derived index*

The record-keeping in R3/R4 does suggest a relational store — but it doesn't have to be the
*system of record*. Split the two roles:

- **System of record:** YAML files in directory trees, each tree optionally a git repo. This keeps
  everything you chose git for: human-readable diffs, PR-based contribution (which *is* the R2
  workflow), no services on HPC, offline operation, and the existing scanner code keeps working.
- **Query layer:** a per-user **SQLite index** (single file, stdlib, zero services) built by
  scanning the stores. It is a **disposable cache** — gitignored, rebuildable from the files at any
  time, never authoritative. All the "list blueprints derived from domainspec X" / "list outputs
  for domainspec X" queries run against it. If it's ever corrupt or stale: delete and rescan.

Why not a real client-server or even SQLite-as-canonical DB:
- Multi-writer SQLite on Lustre/NFS is exactly where its locking breaks; a per-user local index
  sidesteps that entirely because concurrent writers never share the DB file.
- A canonical DB kills the git contribution flow (R2) and makes HPC support (R5) hard — the user
  already identified this; the survey found nothing that changes that judgment.
- If scale ever demands it (institutional registry, web UI), the derived-index design upgrades
  cleanly: point the same indexer at Postgres. Nothing about the files changes.

Prior art worth borrowing from, not adopting wholesale: **intake/intake-esm** (files+derived
dataframe index over an esm collection — same shape as this proposal), **conda channels**
(precedence-ordered layered sources — §4.2), **STAC** (static JSON catalogs with typed links —
the reference model for §4.3), **DataLad/git-annex** (only if large binary assets ever move into
catalogs — §4.5).

### 4.2 Topology: layered stores (this is also the short-term fix)

A catalog becomes an ordered stack of **stores**, each a plain directory tree:

```
[0] user scratch      ~/cstar-forge-data/catalog          read-write (all writes go here)
[1] group shared      /shared/project/cstar-catalog       read-only via fs, contribute via git PR
[2] packaged/bundled  site-packages/cstar_forge/catalog   always read-only
```

Reads union the layers, and **names must be unique across the whole stack** — no shadowing.
Writers reject a save whose name already exists in *any* layer, so editing a bundled entry means
saving it under a new name. (Decided 2026-08-14: shadowing was considered and rejected — if a
package upgrade ever updates a bundled entry, a same-named user copy would silently mask the
update.) Every listing carries a `source` (which store an entry came from) so the wizard can badge
entries ("bundled" vs "mine" vs "shared"). Writes *always* go to the top (user) layer — the packaged store becomes physically
read-only by policy. A shared store is just a git clone somewhere both colleagues can read
(home dir, project dir on HPC); "contribute" = copy an entry from layer 0 into a clone of layer 1
and push/PR. Later, a `cstar forge catalog contribute <kind> <name>` helper can automate the
copy+branch+PR, but plain git suffices from day one.

This subsumes all three options from the prompt:
- **Layering** is the architecture.
- **Seeding/sync** (option B) survives as the bootstrap for creating a *new* writable store
  (`initialize_catalog_from="local"` already does this), but is not how bundled content stays
  current — the bundled layer updates itself with the package, so there is no re-sync/merge
  problem, and no "user edited a seeded copy, upgrade wants to overwrite it" conflict.
- **External git catalog** (option C) survives as "one of the layers is a clone of a shared repo"
  — but it should not be the *only* mechanism: first-run network dependency and air-gapped HPC
  make clone-on-demand a bad sole default, and docs/tests `{include}` bundled files anyway.

Config surface (resolution order): explicit API arg → `CSTAR_FORGE_CATALOG` env var (path, or
os-pathsep-separated stack) → a small user config (`~/cstar-forge-data/config.yaml` or the
existing `config.paths` machinery, finally giving PR #100's field a consumer) → built-in default
stack `[~/cstar-forge-data/catalog, <packaged>]`.

### 4.3 Prerequisite for R3/R4: real identity and typed references

Relationship queries can't be built on "directory name + filename regex". Two additive changes:

1. **Stable entry identity.** Give every catalog entry (and every forge blueprint) an `id` — a
   creation-time UUID (or `name@<short-hash>`) plus the existing human name. IDs are minted once
   and never recomputed, so they don't suffer the content-hash-churn problem in §2. Content hashes
   remain useful as *integrity/dedup* fingerprints once canonicalized (exclude-`None` before
   hashing), but the join key is the ID.
2. **Typed references.** Extend `PieceRef` to carry the source entry's `id` (and the content hash
   of what was snapshotted) alongside `name/origin/modified`. The snapshot-don't-reference rule is
   untouched — the blueprint still inlines resolved values; the ref is provenance metadata that the
   indexer turns into graph edges. Same pattern for `Domain.yaml: model_name` → `model_id`.

With those, the SQLite index is trivial: `entries(id, kind, name, store, path, content_hash, ...)`
+ `edges(from_id, to_id, relation)`; both directions of R3 are one query.

### 4.4 R4: downstream outputs report back via breadcrumbs, not a service

C-Star processes shouldn't write into a live database (HPC, permissions, concurrency). Instead the
executor/run machinery drops a small **run manifest** (YAML/JSON: blueprint id + content_hash,
roms_marbl blueprint path, output URIs, machine, timestamps, status) at a well-known place — in the
run's working dir and/or appended into a `runs/` area of the user's scratch store. The indexer
ingests manifests exactly like catalog entries. "Given a domainspec, show all outputs" is then
domainspec —edge→ blueprints —edge→ run manifests —→ output paths. This respects the existing
executor/catalog boundary: the executor still never *reads* the catalog; it only emits one more
self-describing artifact. (The emitted roms_marbl blueprint already carries most of this; the
manifest mainly adds the forge-blueprint id and output locations.)

### 4.5 Assets (later): make blueprints-with-files portable

Once user stores exist, the netcdfs-branch transport gap has a natural fix: an opt-in
"import into catalog" that copies an attached file into the user store's assets area keyed by
content hash, and lets `UserProvidedFile.location` be a catalog-asset reference in addition to an
absolute path. The `add_asset_to_domain` machinery is a starting point. Large-file hygiene in
shared git stores would then need git-lfs/DataLad or an "assets stay out of git" policy — decide
when it becomes real.

## 5. Short-term plan (concrete)

Land after `user-provided-netcdfs` merges. Scope: minimal two-layer catalog + write redirection.

1. **`CatalogStore` / layered `DomainCatalog`.** Refactor `DomainCatalog` so the existing
   fsspec-scanning logic becomes a single-store class, and `DomainCatalog` holds an ordered list of
   stores with union reads, top-layer writes, and per-entry `source` attribution. Default stack:
   `[~/cstar-forge-data/catalog (created lazily), packaged]`. Honor `CSTAR_FORGE_CATALOG`.
   (Degenerate single-store mode keeps current tests/back-compat working.)
2. **Redirect all writes to the user layer**: `_default_blueprint_path`, `_workplan_dest`, and the
   four `register_*` writers. Writers refuse to target a read-only store, and enforce
   stack-wide name uniqueness (editing a bundled entry ⇒ save under a new name; the wizard
   should prompt for one rather than erroring). Fixes the GitHub-writer
   CWD bug as a side effect.
3. **Wizard**: show layer badges in dropdowns; Catalog bar accepts a stack (or at least "your
   catalog" + "include bundled" toggle).
4. **Cheap adjacent fixes**: lazy `default_catalog` (module `__getattr__`) to kill the import-time
   scan; add a forge-blueprint scanner (or fix `_scan_roms_marbl_blueprints`'s layout mismatch);
   delete or wire up `config.paths.catalog` so the vestige stops confusing people; explicit
   package-data include for the catalog tree.
5. **Docs**: getting-started + machine-config updates ("your work lives in
   `~/cstar-forge-data/catalog`"); migration note for anyone with blueprints stranded in
   site-packages (a one-liner copy, since blueprints are self-contained).

Deliberately *not* in the short-term slice: IDs/typed refs (§4.3), SQLite index, contribute
helper, run manifests, asset import. Each is additive on top of the layered-store base, which is
the point: the short-term fix is step one of the long-term architecture, not a throwaway.

## 6. Open questions

- User-store default location: keep `~/cstar-forge-data/catalog` (already in config + docs) vs
  platformdirs (`~/.local/share/cstar-forge/catalog`)? Recommend keeping `~/cstar-forge-data` —
  it's discoverable, already documented, and scientists find dot-dirs annoying on HPC.
- Should the bundled catalog eventually shrink to a pure demo set, with the "real" curated catalog
  becoming a shared git store (option C as destination state)? Plausible, but only after the
  layered mechanism exists and a public catalog repo is stood up (the fsspec GitHub read path and
  the commented-out `CWorthy-Demo` tests suggest this was already the intended direction).
- ID scheme details (UUID vs name@hash), and whether IDs get stamped retroactively on bundled
  entries at first index build.
