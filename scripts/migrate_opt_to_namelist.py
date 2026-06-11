#!/usr/bin/env python3
"""
Migrate a legacy filled ``.opt`` + ``roms.in`` build into the new
``cppdefs.opt`` + ``namelist.nml`` format.

Background
----------
Before the namelist refactor, a ROMS-MARBL build directory held ~14 rendered
Fortran ``*.opt`` files plus a positional ``roms.in``. The current system emits
just two files: ``cppdefs.opt`` (compile-time CPP defines, still Jinja2) and
``namelist.nml`` (everything else, written by ``write_roms_namelist`` via f90nml).

This script reads an old build's ``*.opt`` files and ``roms.in``, recovers the
settings into the current flat run-time dict + cppdefs dict, and re-emits
``cppdefs.opt`` + ``namelist.nml`` using the *same* forge machinery
(``render_roms_settings`` and ``write_roms_namelist``) so the output is
guaranteed to match what a fresh forge run would produce.

Strategy
--------
Start from the current model defaults (a complete, valid skeleton — so new
namelist-only sections that had no old file get sensible defaults and nothing
KeyErrors), then overlay every value we can recover from the legacy files.
Anything unparseable falls back to the default and is reported as a warning.

Usage
-----
    # convert files only
    python scripts/migrate_opt_to_namelist.py OLD_BUILD_DIR OUTPUT_DIR
    python scripts/migrate_opt_to_namelist.py --opt-dir DIR --roms-in FILE OUTPUT_DIR

    # convert files AND rewrite blueprint (B_*.yml) code filters in the same dir
    python scripts/migrate_opt_to_namelist.py CASE_DIR OUTPUT_DIR --update-blueprints

    # only rewrite blueprint filters (no file conversion)
    python scripts/migrate_opt_to_namelist.py --blueprints-dir CASE_DIR --update-blueprints

``OLD_BUILD_DIR`` is searched recursively for ``cppdefs.opt`` (locating the
``*.opt`` directory) and ``roms.in``. ``--update-blueprints`` scans the input
directory (or ``--blueprints-dir``) recursively for blueprint YAML files —
names starting with ``B_`` or containing ``blueprint`` (case-insensitive),
``.yml`` or ``.yaml`` — and writes a migrated copy of each into ``OUTPUT_DIR``
(originals are never modified). Each copy's ``code.compile_time``/
``code.run_time`` file filters are rewritten: drop every ``*.opt`` except
``cppdefs.opt``; drop ``roms.in`` and the dead ``marbl_tracer_output_list`` /
``marbl_diagnostic_output_list`` files; add ``namelist.nml`` (other entries
such as ``marbl_in`` are left as-is).

Limitations (reported at runtime where relevant)
------------------------------------------------
* The ``roms.in`` forcing block is an unlabeled ordered list; entries are
  re-assigned to surface/boundary/tidal/river slots by filename heuristic.
* ``surf_flux.opt`` ``dSSTdt``/``dSSSdt`` were CPP-gated Fortran *expressions*
  (e.g. ``7.777/(100.*86400.)``); they are NOT migrated — sss/sst correction
  keep their (0.0) defaults. A warning is emitted if QCORRECTION/SFLX_CORR was on.
* CPP-conditional integers (e.g. ``ntrc_bio`` under BIOLOGY_BEC2) recover the
  MARBL branch value.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

import cstar_forge  # noqa: F401  (for package path)
from cstar_forge.settings import render_roms_settings, write_roms_namelist

_PKG = Path(cstar_forge.__file__).parent
_MARBL_TPL = _PKG / "catalog" / "ModelSpec" / "cson_roms-marbl_v0.1" / "templates"

_WARNINGS: list[str] = []


def _warn(msg: str) -> None:
    _WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


# ---------------------------------------------------------------------------
# Fortran parsing helpers
# ---------------------------------------------------------------------------
def _parse_fortran_value(raw: str):
    """Convert a Fortran literal token to a Python bool/int/float/str, or None."""
    s = raw.strip().strip(",").strip()
    low = s.lower()
    if low in (".true.", "t", ".t."):
        return True
    if low in (".false.", "f", ".f."):
        return False
    m = re.fullmatch(r"'([^']*)'", s) or re.fullmatch(r'"([^"]*)"', s)
    if m:
        return m.group(1)
    # numeric: handle Fortran double-precision exponent (1.0D0, 250D0) and reals
    num = re.sub(r"[dD]", "e", s)
    if re.fullmatch(r"[+-]?\d+", s):
        return int(s)
    try:
        return float(num)
    except ValueError:
        return None


def _normalize_opt(text: str) -> str:
    """Strip ``!`` comments and join leading-``&`` Fortran continuation lines."""
    out: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"!.*$", "", line)
        if re.match(r"\s*&", line):
            cont = re.sub(r"^\s*&", " ", line)
            if out:
                out[-1] += cont
            else:
                out.append(cont)
        else:
            out.append(line)
    return "\n".join(out)


_VALUE_TOKEN = r"(\.true\.|\.false\.|'[^']*'|[A-Za-z0-9_.+\-]+)"


def _opt_scalar(text: str, key: str):
    """Return the first parseable value of ``key = <value>`` in normalized text."""
    for tok in re.findall(rf"\b{re.escape(key)}\s*=\s*{_VALUE_TOKEN}", text):
        val = _parse_fortran_value(tok)
        if val is not None:
            return val
    return None


# (file stem, target run-time section, {opt_var: dict_key})
# opt_var == dict_key unless noted. Only keys consumed by write_roms_namelist
# (plus those needed to derive n_tracers / calc_pflx) are listed.
_OPT_SECTIONS = [
    ("param", "param", {k: k for k in
        ["LLm", "MMm", "N", "NP_XI", "NP_ETA", "NSUB_X", "NSUB_E", "nt_passive", "ntrc_bio"]}),
    ("blk_frc", "blk_frc", {"interp_frc": "interp_frc", "do_check_units": "check_bulk_frc_units"}),
    ("bgc", "bgc", {k: k for k in
        ["wrt_his", "output_period_his", "nrpf_his", "wrt_avg", "output_period_avg", "nrpf_avg",
         "wrt_his_dia", "output_period_his_dia", "nrpf_his_dia",
         "wrt_avg_dia", "output_period_avg_dia", "nrpf_avg_dia", "interp_frc"]}),
    ("tides", "tides", {k: k for k in ["ntides", "bry_tides", "pot_tides", "ana_tides"]}),
    ("river_frc", "river_frc", {k: k for k in ["river_source", "analytical", "nriv"]}),
    ("ocean_vars", "ocean_vars", {k: k for k in
        ["wrt_file_rst", "output_period_rst", "monthly_restarts", "nrpf_rst",
         "wrt_file_his", "output_period_his", "nrpf_his",
         "wrt_Z", "wrt_Ub", "wrt_Vb", "wrt_U", "wrt_V", "wrt_R", "wrt_O", "wrt_W",
         "wrt_Akv", "wrt_Akt", "wrt_Aks", "wrt_Hbls", "wrt_Hbbl",
         "wrt_file_avg", "output_period_avg", "nrpf_avg",
         "wrt_avg_Z", "wrt_avg_Ub", "wrt_avg_Vb", "wrt_avg_U", "wrt_avg_V", "wrt_avg_R",
         "wrt_avg_O", "wrt_avg_W", "wrt_avg_Akv", "wrt_avg_Akt", "wrt_avg_Aks",
         "wrt_avg_Hbls", "wrt_avg_Hbbl", "code_check"]}),
    ("surf_flux", "surf_flux", {k: k for k in
        ["wrt_smflx", "wrt_stflx", "wrt_swflx", "sflx_avg", "output_period", "nrpf"]}),
    ("diagnostics", "diagnostics", {k: k for k in
        ["diag_avg", "output_period", "nrpf", "diag_uv", "diag_trc", "diag_pflx", "timescale"]}),
    ("cdr_frc", "cdr_frc", {k: k for k in
        ["cdr_source", "cdr_file", "ncdr_parm", "forcing_depth_profiles", "forcing_3d",
         "forcing_parameterized", "time_interpolation", "relocate_to_wet_pts",
         "cdr_volume", "nz_chd"]}),
    ("cdr_output", "cdr_output", {k: k for k in
        ["do_cdr", "do_avg", "monthly_averages", "output_period", "nrpf"]}),
    ("extract_data", "extract_data", {k: k for k in
        ["do_extract", "extract_file", "nrpf", "N_chd", "theta_s_chd", "theta_b_chd",
         "hc_chd", "extract_period"]}),
    ("sponge_tune", "sponge_tune", {k: k for k in
        ["ub_tune", "spn_avg", "sp_timscale", "wrt_sponge", "nrpf", "output_period"]}),
    ("upscale_output", "upscale_output", {k: k for k in
        ["do_upscale", "nrpf_uscl", "output_period_uscl"]}),
]


def _load_defaults():
    """Load the current model defaults as a complete settings skeleton."""
    ct = yaml.safe_load((_MARBL_TPL / "compile-time-defaults.yml").read_text())
    rt = yaml.safe_load((_MARBL_TPL / "run-time-defaults.yml").read_text())
    return ct, rt


# ---------------------------------------------------------------------------
# .opt ingestion
# ---------------------------------------------------------------------------
def ingest_opt_files(opt_dir: Path, ct: dict, rt: dict) -> None:
    for stem, section, keymap in _OPT_SECTIONS:
        path = opt_dir / f"{stem}.opt"
        if not path.is_file():
            _warn(f"{stem}.opt not found in {opt_dir}; keeping defaults for [{section}]")
            continue
        text = _normalize_opt(path.read_text())
        rt.setdefault(section, {})
        for opt_var, dict_key in keymap.items():
            val = _opt_scalar(text, opt_var)
            if val is not None:
                rt[section][dict_key] = val

    # diagnostics.diag_pflx / timescale feed the new calc_pflx section
    diag = rt.get("diagnostics", {})
    if "diag_pflx" in diag:
        rt.setdefault("calc_pflx", {})["calc_pflx"] = bool(diag["diag_pflx"])
    if "timescale" in diag:
        rt.setdefault("calc_pflx", {})["timescale"] = float(diag["timescale"])

    # cppdefs flags from cppdefs.opt (presence of an uncommented #define)
    cpp_path = opt_dir / "cppdefs.opt"
    if cpp_path.is_file():
        cpp = cpp_path.read_text()

        def _defined(flag: str) -> bool:
            return re.search(rf"^\s*#\s*define\s+{flag}\b", cpp, re.MULTILINE) is not None

        ct.setdefault("cppdefs", {})
        ct["cppdefs"]["obc_west"] = _defined("OBC_WEST")
        ct["cppdefs"]["obc_east"] = _defined("OBC_EAST")
        ct["cppdefs"]["obc_north"] = _defined("OBC_NORTH")
        ct["cppdefs"]["obc_south"] = _defined("OBC_SOUTH")
        ct["cppdefs"]["marbl"] = _defined("MARBL")
        ct["cppdefs"]["cdr_forcing"] = _defined("CDR_FORCING")
        ct["cppdefs"]["co2_tvarying"] = _defined("PCO2AIR_FORCING")
        if _defined("SFLX_CORR"):
            ct["cppdefs"]["sal_restore"] = True
            _warn("SFLX_CORR was defined: sss_correction.dSSSdt is not recovered "
                  "from surf_flux.opt (gated expression); left at default 0.0")
        if _defined("QCORRECTION"):
            _warn("QCORRECTION was defined: sst_correction.dSSTdt is not recovered "
                  "from surf_flux.opt (gated expression); left at default 0.0")
    else:
        _warn(f"cppdefs.opt not found in {opt_dir}; keeping default cppdefs flags")


# ---------------------------------------------------------------------------
# roms.in ingestion (positional / sectioned)
# ---------------------------------------------------------------------------
_FORCING_KEYS = [
    "surface_forcing_path", "surface_forcing_bgc_path",
    "boundary_forcing_path", "boundary_forcing_bgc_path",
    "tidal_forcing_path", "river_path",
]


def _classify_forcing(path: str) -> str | None:
    p = path.lower()
    if "surface" in p and "bgc" in p:
        return "surface_forcing_bgc_path"
    if "surface" in p:
        return "surface_forcing_path"
    if "boundary" in p and "bgc" in p:
        return "boundary_forcing_bgc_path"
    if "boundary" in p:
        return "boundary_forcing_path"
    if "tidal" in p or "tides" in p:
        return "tidal_forcing_path"
    if "river" in p:
        return "river_path"
    return None


def _roms_in_sections(text: str) -> dict[str, list[str]]:
    """Split roms.in into {header_word: [value lines]} (headers start at col 0)."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        # a header line starts in column 0 and looks like ``name:``
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if m and not line[0].isspace():
            current = m.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line.strip())
    return sections


def _nums(line: str) -> list[float]:
    out = []
    for tok in line.replace(",", " ").split():
        v = _parse_fortran_value(tok)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
    return out


def ingest_roms_in(roms_in: Path, rt: dict) -> None:
    sec = _roms_in_sections(roms_in.read_text())

    def first(name):
        v = sec.get(name) or []
        return v[0] if v else None

    if first("title"):
        rt.setdefault("title", {})["casename"] = first("title")
    if sec.get("time_stepping"):
        n = _nums(sec["time_stepping"][0])
        if len(n) >= 4:
            rt.setdefault("time_stepping", {}).update(
                ntimes=int(n[0]), dt=n[1], ndtfast=int(n[2]), ninfo=int(n[3]))
    if sec.get("S-coord"):
        n = _nums(sec["S-coord"][0])
        if len(n) >= 3:
            rt.setdefault("s_coord", {}).update(theta_s=n[0], theta_b=n[1], tcline=n[2])
    if first("grid"):
        rt.setdefault("grid", {})["grid_file"] = first("grid")

    # forcing: unlabeled ordered list -> reassign by filename heuristic
    forcing_paths = sec.get("forcing") or []
    if forcing_paths:
        rt.setdefault("forcing", {})
        for k in _FORCING_KEYS:
            rt["forcing"][k] = None
        for p in forcing_paths:
            key = _classify_forcing(p)
            if key is None:
                _warn(f"could not classify forcing path (left out of frcfile): {p}")
                continue
            if rt["forcing"].get(key) is not None:
                _warn(f"multiple forcing paths matched '{key}'; keeping first, dropping: {p}")
                continue
            rt["forcing"][key] = p

    if sec.get("initial"):
        vals = sec["initial"]
        if vals:
            rt.setdefault("initial", {})
            nrrec = _parse_fortran_value(vals[0])
            if isinstance(nrrec, int):
                rt["initial"]["nrrec"] = nrrec
            if len(vals) >= 2:
                rt["initial"]["initial_file"] = vals[1]
    if first("output_root_name"):
        rt.setdefault("output_root_name", {})["output_root_name"] = first("output_root_name")
    if sec.get("lateral_visc"):
        n = _nums(sec["lateral_visc"][0])
        if len(n) >= 1:
            rt.setdefault("lateral_visc", {})["visc2"] = n[0]
        if len(n) >= 2:
            rt["lateral_visc"]["visc4"] = n[1]
    if first("rho0"):
        n = _nums(first("rho0"))
        if n:
            rt.setdefault("lateral_visc", {})["rho0"] = n[0]
    if sec.get("vertical_mixing"):
        n = _nums(sec["vertical_mixing"][0])
        if n:
            rt.setdefault("vertical_mixing", {})["akv"] = n[0]
            rt["vertical_mixing"]["akt_default"] = n[1] if len(n) > 1 else n[0]
    if sec.get("tracer_diff2"):
        n = _nums(sec["tracer_diff2"][0])
        if n:
            rt.setdefault("tracer_diff2", {})["tnu2_default"] = n[0]
    if sec.get("bottom_drag"):
        n = _nums(sec["bottom_drag"][0])
        bd = rt.setdefault("bottom_drag", {})
        for key, val in zip(["rdrg", "rdrg2", "zob", "cdb_min", "cdb_max"], n):
            bd[key] = val
    if first("v_sponge"):
        n = _nums(first("v_sponge"))
        if n:
            rt.setdefault("v_sponge", {})["v_sponge"] = n[0]
    if first("gamma2"):
        n = _nums(first("gamma2"))
        if n:
            rt["gamma2"] = n[0]
    if first("ubind"):
        n = _nums(first("ubind"))
        if n:
            rt["ubind"] = n[0]


# ---------------------------------------------------------------------------
# Blueprint filter rewriting
# ---------------------------------------------------------------------------
# Run-time files that the namelist format no longer produces.
_DEAD_RUNTIME_FILES = ("roms.in", "marbl_tracer_output_list", "marbl_diagnostic_output_list")


def update_blueprint(src: Path, dest: Path) -> str:
    """
    Read a blueprint, rewrite its ``code`` filters to the namelist format, and
    write the result to ``dest`` (the original ``src`` is never modified).

    * compile_time: drop every ``*.opt`` except ``cppdefs.opt``.
    * run_time: drop ``roms.in`` and the dead ``marbl_*_output_list`` files;
      add ``namelist.nml``.

    Other entries (``marbl_in``, etc.) are left untouched. Files without a
    rewritable ``code`` section are copied through verbatim. The output is
    serialized exactly like forge does
    (``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)``), which
    round-trips these blueprints byte-for-byte. Returns a one-line status.
    """
    raw = src.read_text()
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _copy_through(note: str) -> str:
        if dest.resolve() != src.resolve():
            dest.write_text(raw)
        return note

    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or not isinstance(data.get("code"), dict):
        return _copy_through("copied unchanged (no code section)")
    code = data["code"]
    notes: list[str] = []

    ct = code.get("compile_time")
    if isinstance(ct, dict) and isinstance(ct.get("filter"), dict) \
            and isinstance(ct["filter"].get("files"), list):
        old = ct["filter"]["files"]
        new = sorted(f for f in old if not (str(f).endswith(".opt") and f != "cppdefs.opt"))
        if new != old:
            removed = [f for f in old if f not in new]
            ct["filter"]["files"] = new
            notes.append(f"compile_time -{removed}")

    rt = code.get("run_time")
    if isinstance(rt, dict) and isinstance(rt.get("filter"), dict) \
            and isinstance(rt["filter"].get("files"), list):
        old = rt["filter"]["files"]
        new = [f for f in old if f not in _DEAD_RUNTIME_FILES]
        added = "namelist.nml" not in new
        if added:
            new.append("namelist.nml")
        new = sorted(new)
        if new != old:
            sub = [f"-{f}" for f in _DEAD_RUNTIME_FILES if f in old]
            if added:
                sub.append("+namelist.nml")
            rt["filter"]["files"] = new
            notes.append("run_time " + " ".join(sub))

    if not notes:
        return _copy_through("copied unchanged")
    dest.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
    return "migrated (" + "; ".join(notes) + ")"


def _is_blueprint_file(p: Path) -> bool:
    """A YAML file that looks like a blueprint: ``B_*`` (forge convention) or
    any name containing ``blueprint`` (case-insensitive), e.g. ``my_toy_blueprint.yaml``."""
    if p.suffix.lower() not in (".yml", ".yaml"):
        return False
    name = p.name.lower()
    return name.startswith("b_") or "blueprint" in name


def update_blueprints_in(bp_dir: Path, out_dir: Path) -> None:
    blueprints = sorted(p for p in bp_dir.rglob("*") if p.is_file() and _is_blueprint_file(p))
    if not blueprints:
        _warn(f"no blueprint files (B_*.y[a]ml or *blueprint*.y[a]ml) found under {bp_dir}")
        return
    print(f"\n• Migrating {len(blueprints)} blueprint(s) from {bp_dir} -> {out_dir}")
    for bp in blueprints:
        rel = bp.relative_to(bp_dir)
        print(f"  - {rel}: {update_blueprint(bp, out_dir / rel)}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def _find(root: Path, name: str) -> Path | None:
    if (root / name).is_file():
        return root / name
    hits = sorted(root.rglob(name))
    return hits[0] if hits else None


def migrate(opt_dir: Path, roms_in: Path, out_dir: Path) -> None:
    ct, rt = _load_defaults()

    print(f"• Ingesting .opt files from {opt_dir}")
    ingest_opt_files(opt_dir, ct, rt)
    print(f"• Ingesting roms.in from {roms_in}")
    ingest_roms_in(roms_in, rt)

    # n_tracers = temp + salt + passive + bio
    param = rt.get("param", {})
    n_tracers = 2 + int(param.get("nt_passive", 0)) + int(param.get("ntrc_bio", 0))
    print(f"• n_tracers = {n_tracers} (2 + nt_passive={param.get('nt_passive')} "
          f"+ ntrc_bio={param.get('ntrc_bio')})")

    out_dir.mkdir(parents=True, exist_ok=True)

    # namelist.nml
    write_roms_namelist(settings_compile_time=ct, settings_run_time=rt,
                        output_dir=out_dir, n_tracers=n_tracers)
    print(f"✓ wrote {out_dir / 'namelist.nml'}")

    # cppdefs.opt (re-render the current template; merge run-time sections the
    # template gates on, mirroring CstarSpecBuilder.configure_build)
    render_roms_settings(
        template_files=["cppdefs.opt.j2"],
        template_dir=_MARBL_TPL / "compile-time",
        settings_dict={**ct, **rt},
        code_output_dir=out_dir,
        n_tracers=n_tracers,
    )
    print(f"✓ wrote {out_dir / 'cppdefs.opt'}")

    if _WARNINGS:
        print(f"\nCompleted with {len(_WARNINGS)} warning(s) — review the values above.")
    else:
        print("\nCompleted with no warnings.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old_build_dir", nargs="?", type=Path,
                    help="Legacy build dir (searched for cppdefs.opt and roms.in); "
                         "also the default dir scanned for blueprints with --update-blueprints")
    ap.add_argument("output_dir", nargs="?", type=Path,
                    help="Output directory for cppdefs.opt + namelist.nml and the migrated "
                         "blueprint copies (originals are never modified)")
    ap.add_argument("--opt-dir", type=Path, help="Directory containing the .opt files")
    ap.add_argument("--roms-in", type=Path, help="Path to the legacy roms.in")
    ap.add_argument("--update-blueprints", action="store_true",
                    help="Also rewrite blueprint code filters (remove roms.in + old .opt files, "
                         "add namelist.nml). Matches B_*.y[a]ml and *blueprint*.y[a]ml under "
                         "the input dir / --blueprints-dir")
    ap.add_argument("--blueprints-dir", type=Path,
                    help="Directory to scan for blueprint YAML files (default: OLD_BUILD_DIR)")
    args = ap.parse_args(argv)

    # When the source is given explicitly (--opt-dir/--roms-in for conversion, or
    # --blueprints-dir for blueprint-only), a lone positional is the output dir.
    if args.output_dir is None and args.old_build_dir is not None \
            and (args.opt_dir or args.roms_in or args.blueprints_dir is not None):
        args.output_dir, args.old_build_dir = args.old_build_dir, None

    do_blueprints = args.update_blueprints or args.blueprints_dir is not None
    have_conv_inputs = bool(args.old_build_dir or args.opt_dir or args.roms_in)
    do_convert = have_conv_inputs and args.output_dir is not None

    if have_conv_inputs and args.output_dir is None and not do_blueprints:
        ap.error("output_dir is required to convert .opt/roms.in files")
    if do_blueprints and args.output_dir is None:
        ap.error("output_dir is required: migrated blueprints are written there, "
                 "not overwritten in place")
    if not do_convert and not do_blueprints:
        ap.error("nothing to do: give OLD_BUILD_DIR + OUTPUT_DIR to convert, "
                 "and/or --update-blueprints")

    if do_convert:
        opt_dir = args.opt_dir
        roms_in = args.roms_in
        root = args.old_build_dir
        if opt_dir is None:
            cpp = _find(root, "cppdefs.opt") if root else None
            if cpp is None:
                ap.error("could not locate cppdefs.opt; pass --opt-dir")
            opt_dir = cpp.parent
        if roms_in is None:
            roms_in = _find(root, "roms.in") if root else None
            if roms_in is None:
                ap.error("could not locate roms.in; pass --roms-in")
        if not opt_dir.is_dir():
            ap.error(f"opt dir not found: {opt_dir}")
        if not roms_in.is_file():
            ap.error(f"roms.in not found: {roms_in}")
        migrate(opt_dir, roms_in, args.output_dir)

    if do_blueprints:
        bp_dir = args.blueprints_dir or args.old_build_dir
        if bp_dir is None:
            ap.error("--update-blueprints needs --blueprints-dir (or pass OLD_BUILD_DIR)")
        if not bp_dir.is_dir():
            ap.error(f"blueprints dir not found: {bp_dir}")
        update_blueprints_in(bp_dir, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
