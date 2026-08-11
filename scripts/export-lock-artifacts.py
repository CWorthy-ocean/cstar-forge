#!/usr/bin/env python
"""Export plain-conda/pip consumption artifacts from pixi.lock.

pixi.lock is the source of truth for the project's fully-solved dependency
closure (conda layer + pypi layer, per environment and platform). Not every
consumer can run pixi (e.g. some CI/release-asset workflows just want files
to hand to `conda`/`pip`), so this script renders two artifacts per platform
for a given pixi environment:

1. A conda "explicit spec" file (via `pixi workspace export
   conda-explicit-spec`) covering the conda-channel layer.
2. A `requirements-<env>-<platform>.txt` file covering the pypi layer,
   parsed directly out of pixi.lock. The editable `cstar-forge` self-package
   is deliberately excluded (see module docstring in the generated file).

Usage:
    python scripts/export-lock-artifacts.py --env dev --outdir dist/lock-artifacts
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCKFILE = REPO_ROOT / "pixi.lock"
SELF_PACKAGE_NAME = "cstar-forge"


def find_pixi() -> str:
    """Locate the pixi binary: PATH first, then the ~/.pixi/bin fallback."""
    found = shutil.which("pixi")
    if found:
        return found
    fallback = Path.home() / ".pixi" / "bin" / "pixi"
    if fallback.is_file():
        return str(fallback)
    raise SystemExit(
        "Could not find `pixi` on PATH or at ~/.pixi/bin/pixi. "
        "Install pixi (https://pixi.sh) or add it to PATH."
    )


def load_lock(lockfile: Path) -> dict:
    if not lockfile.is_file():
        raise SystemExit(f"pixi.lock not found at {lockfile}")
    with lockfile.open() as f:
        return yaml.safe_load(f)


def platforms_for_env(lock: dict, env: str) -> list[str]:
    try:
        env_packages = lock["environments"][env]["packages"]
    except KeyError as exc:
        available = sorted(lock.get("environments", {}))
        raise SystemExit(
            f"Environment '{env}' not found in pixi.lock. Available: {available}"
        ) from exc
    return sorted(env_packages)


def pypi_metadata_index(lock: dict) -> dict:
    """Map a pypi package identifier (URL or local path) -> its metadata dict."""
    index = {}
    for entry in lock.get("packages", []):
        identifier = entry.get("pypi")
        if identifier is not None:
            index[identifier] = entry
    return index


PYPI_INDEX_PREFIX = "https://files.pythonhosted.org/"


def pypi_requirements_for(lock: dict, env: str, platform: str, index: dict):
    """Return (sorted list of 'name==version' strings, self_package_meta_or_None).

    Every pypi entry in pixi.lock is one of three shapes, handled differently:
      1. The project's own editable install (local path, e.g. `pypi: ./`) --
         excluded from requirements.txt, returned as `self_meta` instead.
      2. A plain PyPI-index wheel/sdist (`pypi: https://files.pythonhosted.org/...`)
         with a resolved name+version -- rendered as `name==version`, since a
         plain `pip install name==version` replay is guaranteed to fetch the
         exact same artifact from the index.
      3. Anything else (a git/direct URL, a *different* local path, a
         non-index host) -- refused with a clear error rather than silently
         emitting `name==version`, which for a non-index source could have
         pip fetch a *different* artifact than the one pixi.lock actually
         resolved, silently breaking fidelity with the lockfile.
    """
    try:
        entries = lock["environments"][env]["packages"][platform]
    except KeyError as exc:
        raise SystemExit(
            f"No packages recorded for env='{env}' platform='{platform}' in pixi.lock"
        ) from exc

    requirements = []
    self_meta = None
    for entry in entries:
        identifier = entry.get("pypi")
        if identifier is None:
            continue  # conda-layer package, not our concern here
        meta = index.get(identifier)
        if meta is None:
            raise SystemExit(
                f"pixi.lock is inconsistent: pypi package '{identifier}' is listed "
                f"under environments.{env}.packages.{platform} but has no matching "
                "entry in the top-level `packages:` section."
            )
        name = meta.get("name")
        version = meta.get("version")
        is_url = identifier.startswith(("http://", "https://"))

        if not is_url:
            if name == SELF_PACKAGE_NAME:
                self_meta = meta
                continue
            raise SystemExit(
                f"pixi.lock has a local/path pypi dependency '{identifier}' "
                f"(name={name!r}) that is not the project's own editable install "
                f"('{SELF_PACKAGE_NAME}'). export-lock-artifacts.py only knows how "
                "to skip the self-package; this needs an explicit carve-out."
            )

        if not identifier.startswith(PYPI_INDEX_PREFIX):
            raise SystemExit(
                f"pypi package '{name}' has identifier '{identifier}', which is not "
                f"a plain PyPI-index wheel/sdist (expected it to start with "
                f"'{PYPI_INDEX_PREFIX}'). It looks like a git/direct-URL install. "
                f"Emitting '{name}=={version}' would have pip fetch a possibly "
                "different artifact from PyPI at replay time, silently breaking "
                "fidelity with pixi.lock -- this needs a manual carve-out (e.g. "
                "document it as its own `pip install <url>` step) rather than a "
                "plain version pin."
            )

        if not name or not version:
            raise SystemExit(
                "Cannot render a pinned requirement for pypi package with "
                f"identifier '{identifier}' (name={name!r}, version={version!r})."
            )
        requirements.append(f"{name}=={version}")

    requirements.sort(key=str.lower)
    return requirements, self_meta


def write_requirements_file(
    outdir: Path,
    env: str,
    platform: str,
    requirements: list[str],
    self_meta: dict | None,
) -> Path:
    spec_name = f"conda-explicit-{env}-{platform}.txt"
    req_name = f"requirements-{env}-{platform}.txt"
    out_path = outdir / req_name

    lines = [
        f"# Generated by scripts/export-lock-artifacts.py from pixi.lock (env={env}, platform={platform})",
        "# Do not edit by hand -- regenerate with:",
        f"#   python scripts/export-lock-artifacts.py --env {env} --outdir <dir>",
        "#",
        "# Replay recipe (paired with the conda-explicit-*.txt file from the same run):",
        f"#   conda create -n cstar-forge-env --file {spec_name}",
        "#   conda install -n cstar-forge-env pip  # pixi's pypi installer is uv-based,",
        "#                                         # so pip is NOT in the explicit spec",
        "#   conda activate cstar-forge-env",
        f"#   python -m pip install --no-deps -r {req_name}",
        "#",
        "# --no-deps is intentional: this file is the complete resolved pypi-layer",
        "# closure for this environment/platform, and pip must not re-resolve it.",
        "# `python -m pip` (not bare `pip`) so the env's own interpreter/pip is used,",
        "# even if some other pip is earlier on PATH.",
        "",
        *requirements,
        "",
    ]

    self_name = (
        self_meta.get("name", SELF_PACKAGE_NAME) if self_meta else SELF_PACKAGE_NAME
    )
    lines += [
        f"# NOTE: '{self_name}' itself is intentionally excluded above (it is the",
        "# editable/local project being packaged, not a pinned third-party pypi release).",
        "# Install it separately, either:",
        "#   python -m pip install -e . --no-deps",
        "# or, once a release is published to PyPI:",
        f"#   python -m pip install {self_name}==<version>",
    ]

    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def run_conda_explicit_spec(
    pixi_bin: str, env: str, platform: str, outdir: Path
) -> Path:
    cmd = [
        pixi_bin,
        "workspace",
        "export",
        "conda-explicit-spec",
        "-e",
        env,
        "-p",
        platform,
        "--ignore-pypi-errors",
        str(outdir),
    ]
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(
            f"`{' '.join(cmd)}` failed (exit {result.returncode}):\n{result.stderr}"
        )

    # pixi names its output `<env>_<platform>_conda_spec.txt`; rename it to match
    # this script's `conda-explicit-<env>-<platform>.txt` / `requirements-<env>-<platform>.txt`
    # naming convention so the two artifacts for a given (env, platform) pair are obvious siblings.
    produced = outdir / f"{env}_{platform}_conda_spec.txt"
    if not produced.is_file():
        raise SystemExit(
            f"Expected pixi to produce {produced}, but it did not. "
            f"pixi stdout:\n{result.stdout}\npixi stderr:\n{result.stderr}"
        )
    target = outdir / f"conda-explicit-{env}-{platform}.txt"
    produced.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export plain conda/pip consumption artifacts (conda explicit spec + "
            "pinned pypi requirements file) from pixi.lock, per platform, for a "
            "given pixi environment."
        )
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["default", "dev", "user"],
        help="pixi environment to export.",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        type=Path,
        help="Directory to write artifacts into (created if missing).",
    )
    args = parser.parse_args()

    pixi_bin = find_pixi()
    lock = load_lock(LOCKFILE)
    platforms = platforms_for_env(lock, args.env)
    if not platforms:
        raise SystemExit(
            f"No platforms found for environment '{args.env}' in pixi.lock"
        )

    index = pypi_metadata_index(lock)
    args.outdir.mkdir(parents=True, exist_ok=True)

    for platform in platforms:
        spec_path = run_conda_explicit_spec(pixi_bin, args.env, platform, args.outdir)
        requirements, self_meta = pypi_requirements_for(lock, args.env, platform, index)
        if not requirements and self_meta is None:
            # Pure-conda environment (the `user` env end state): the explicit
            # spec alone IS the complete environment — no companion pip step.
            print(
                f"[{args.env}/{platform}] wrote {spec_path.name} "
                "(pure-conda environment; no requirements file needed)"
            )
            continue
        req_path = write_requirements_file(
            args.outdir, args.env, platform, requirements, self_meta
        )
        print(
            f"[{args.env}/{platform}] wrote {spec_path.name} and "
            f"{req_path.name} ({len(requirements)} pinned pypi packages)"
        )


if __name__ == "__main__":
    main()
