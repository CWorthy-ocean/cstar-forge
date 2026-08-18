#!/bin/bash
# Script to setup forge development environment
#
# Usage:
#   ./dev-setup.sh                          # Normal setup (creates environment if it doesn't exist)
#   ./dev-setup.sh --clean                  # Remove and rebuild the environment
#   ./dev-setup.sh --batch                  # Run without user prompts (for CI/automation)
#   ./dev-setup.sh --clean --batch          # Clean rebuild without prompts
#   ./dev-setup.sh --with-compilers         # Also install compilers/mpich/netcdf-fortran, no prompt
#   ./dev-setup.sh --roms-tools-ref abc1234  # pip install roms-tools from that git ref
#   ./dev-setup.sh --c-star-ref main         # pip install C-Star from that git ref
#   (refs are branch names or full commit hashes; default for both is main)
#
# roms-tools and C-Star are installed from GitHub with `pip install --no-deps`, so
# pip never resolves or replaces the conda-forge dependency tree (all dependencies
# come from environment.yml).
#
# Package Manager:
#   Uses micromamba if available, then mamba, then conda. If none are found, the
#   script downloads and installs micromamba locally to ./bin (no root required).
#
# HPC hardening (PYTHONNOUSERSITE, env-active assertions) lives in
# scripts/harden-env.sh (sourced below); Jupyter kernel registration is done
# by the installed package itself, via `cstar forge register-kernel`
# (cstar_forge/register_kernel.py).
#
# Prefer pixi? `pixi install` sets up the same environment from pyproject.toml
# without any of this script; see docs/installation.md.

set -e  # Exit on error

CLEAN_MODE=false
BATCH_MODE=false
WITH_COMPILERS=false
ROMS_TOOLS_GIT_REF="main"
C_STAR_GIT_REF="main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean) CLEAN_MODE=true; shift ;;
    --batch|-f|--force) BATCH_MODE=true; shift ;;
    --with-compilers) WITH_COMPILERS=true; shift ;;
    --roms-tools-ref=*) ROMS_TOOLS_GIT_REF="${1#*=}"; shift ;;
    --roms-tools-ref)
      if [[ $# -lt 2 ]]; then echo "Error: --roms-tools-ref requires a value" >&2; exit 1; fi
      ROMS_TOOLS_GIT_REF="$2"; shift 2 ;;
    --c-star-ref=*) C_STAR_GIT_REF="${1#*=}"; shift ;;
    --c-star-ref)
      if [[ $# -lt 2 ]]; then echo "Error: --c-star-ref requires a value" >&2; exit 1; fi
      C_STAR_GIT_REF="$2"; shift 2 ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--clean] [--batch] [--with-compilers] [--roms-tools-ref REF] [--c-star-ref REF]" >&2
      exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/harden-env.sh
source "$SCRIPT_DIR/scripts/harden-env.sh"

env_file="environment.yml"
KERNEL_NAME="$(awk -F': *' '$1=="name"{print $2; exit}' "$env_file" 2>/dev/null)"
if [[ -z ${KERNEL_NAME:-} ]]; then
  echo "Error: Could not determine environment name from ${env_file}." >&2
  exit 1
fi

LOCAL_BIN_DIR="$SCRIPT_DIR/bin"
LOCAL_MICROMAMBA="$LOCAL_BIN_DIR/micromamba"

# Determine OS/arch for the local-micromamba download fallback.
OS_TYPE=""
ARCH_TYPE=""
case "$(uname -s)" in
  Darwin)
    OS_TYPE="osx"
    case "$(uname -m)" in
      arm64) ARCH_TYPE="arm64" ;;
      *) ARCH_TYPE="64" ;;
    esac
    ;;
  Linux)
    OS_TYPE="linux"
    case "$(uname -m)" in
      aarch64) ARCH_TYPE="aarch64" ;;
      *) ARCH_TYPE="64" ;;
    esac
    ;;
  *) OS_TYPE="linux"; ARCH_TYPE="64" ;;
esac
MICROMAMBA_URL="https://micro.mamba.pm/api/micromamba/${OS_TYPE}-${ARCH_TYPE}/latest"

# Detect an already-available package manager (micromamba > mamba > conda).
# No downloads happen here — that's deferred below, after the confirmation
# prompt, and only if nothing was found.
PACKAGE_MANAGER=""
MICROMAMBA_CMD=""
CONDA_LIKE_CMD="conda"
PM_SOURCE="detected"
if command -v micromamba >/dev/null 2>&1; then
  PACKAGE_MANAGER="micromamba"; MICROMAMBA_CMD="micromamba"
elif command -v mamba >/dev/null 2>&1; then
  PACKAGE_MANAGER="mamba"; CONDA_LIKE_CMD="mamba"
elif command -v conda >/dev/null 2>&1; then
  PACKAGE_MANAGER="conda"; CONDA_LIKE_CMD="conda"
elif [[ -f "$LOCAL_MICROMAMBA" && -x "$LOCAL_MICROMAMBA" ]]; then
  PACKAGE_MANAGER="micromamba"; MICROMAMBA_CMD="$LOCAL_MICROMAMBA"
fi

echo ""
echo "Installation Information"
echo "========================="
echo "  OS:               $(uname -s) ($(uname -m))"
echo "  Environment:      $KERNEL_NAME  (from $env_file)"
echo "  Package manager:  ${PACKAGE_MANAGER:-none found — will install micromamba locally to $LOCAL_BIN_DIR}"
echo "  roms-tools (pip): git ref $ROMS_TOOLS_GIT_REF (--no-deps)"
echo "  C-Star (pip):     git ref $C_STAR_GIT_REF (--no-deps)"
echo "  Clean mode:       $CLEAN_MODE"
echo "  Batch mode:       $BATCH_MODE"
echo "  With compilers:   $WITH_COMPILERS"
if [[ "$PACKAGE_MANAGER" == "conda" ]]; then
  echo "  Note: conda installs can be slow; mamba/micromamba is recommended (or --batch for CI)."
fi
echo ""
if [[ "$BATCH_MODE" != "true" ]]; then
  read -r -p "Press Enter to continue, or Ctrl+C to cancel: "
  echo ""
fi

# Last resort: download micromamba locally, then try an HPC `module load conda`.
if [[ -z "$PACKAGE_MANAGER" ]]; then
  if [[ -n "$OS_TYPE" && -n "$ARCH_TYPE" ]]; then
    echo "No micromamba/mamba/conda found. Installing micromamba locally to $LOCAL_BIN_DIR..."
    mkdir -p "$LOCAL_BIN_DIR"
    TEMP_DIR=$(mktemp -d)
    if curl -Ls "$MICROMAMBA_URL" | tar -xvj -C "$TEMP_DIR" bin/micromamba 2>/dev/null; then
      mv "$TEMP_DIR/bin/micromamba" "$LOCAL_MICROMAMBA"
      rm -rf "$TEMP_DIR"
      chmod +x "$LOCAL_MICROMAMBA"
      PACKAGE_MANAGER="micromamba"
      MICROMAMBA_CMD="$LOCAL_MICROMAMBA"
      PM_SOURCE="installed"
      echo "✓ micromamba installed successfully to $LOCAL_BIN_DIR"
    else
      rm -rf "$TEMP_DIR"
      echo "Warning: Failed to download micromamba. Falling back to conda if available."
    fi
  fi
  if [[ -z "$PACKAGE_MANAGER" ]] && command -v module >/dev/null 2>&1; then
    module load conda 2>/dev/null || true
    if command -v conda >/dev/null 2>&1; then
      PACKAGE_MANAGER="conda"; CONDA_LIKE_CMD="conda"
    fi
  fi
fi

if [[ -z "$PACKAGE_MANAGER" ]]; then
  echo "Error: None of micromamba, mamba, or conda are available." >&2
  echo "The script attempted to install micromamba locally but failed." >&2
  echo "Please install miniconda/anaconda for conda support, or install micromamba manually." >&2
  exit 1
fi

if [[ "$PM_SOURCE" == "installed" ]]; then
  echo "Using $PACKAGE_MANAGER as package manager (installed locally in this run)..."
else
  echo "Using $PACKAGE_MANAGER as package manager (detected)..."
fi

#--------------------------------------------------------
# Conda environment: create (or reuse) from environment.yml, then activate
#--------------------------------------------------------
set +u  # package manager activation/deactivation scripts may reference unset vars
if [[ "$PACKAGE_MANAGER" == "micromamba" ]]; then
  if [[ "$MICROMAMBA_CMD" != "micromamba" ]]; then
    alias micromamba="$MICROMAMBA_CMD"
  fi
  eval "$("$MICROMAMBA_CMD" shell hook --shell bash)"

  if "$MICROMAMBA_CMD" env list | awk '{print $1}' | grep -q "^$KERNEL_NAME$"; then
    ENV_EXISTS="true"
  else
    ENV_EXISTS="false"
  fi
  if [[ "$CLEAN_MODE" == "true" && "$ENV_EXISTS" == "true" ]]; then
    echo "Removing existing $PACKAGE_MANAGER environment: $KERNEL_NAME"
    # mamba_trash.txt errors are harmless (conda-meta dir removed before micromamba
    # can write the trash file); the environment removal still succeeds.
    { "$MICROMAMBA_CMD" env remove -n "$KERNEL_NAME" -y 2>&1; } | grep -v "mamba_trash.txt" || true
    sleep 0.5
    ENV_EXISTS="false"
  fi
  if [[ "$ENV_EXISTS" == "false" ]]; then
    echo "Creating $PACKAGE_MANAGER environment: $KERNEL_NAME"
    "$MICROMAMBA_CMD" env create -f "$env_file" -y
  fi
  echo "Activating $PACKAGE_MANAGER environment: $KERNEL_NAME"
  micromamba activate "$KERNEL_NAME"
else
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if "$CONDA_LIKE_CMD" env list | awk '{print $1}' | grep -q "^$KERNEL_NAME$"; then
    ENV_EXISTS="true"
  else
    ENV_EXISTS="false"
  fi
  if [[ "$CLEAN_MODE" == "true" && "$ENV_EXISTS" == "true" ]]; then
    echo "Removing existing $PACKAGE_MANAGER environment: $KERNEL_NAME"
    "$CONDA_LIKE_CMD" env remove -n "$KERNEL_NAME" -y 2>&1 | grep -v "mamba_trash.txt" || true
    sleep 0.5
    ENV_EXISTS="false"
  fi
  if [[ "$ENV_EXISTS" == "false" ]]; then
    echo "Creating $PACKAGE_MANAGER environment: $KERNEL_NAME"
    "$CONDA_LIKE_CMD" env create -f "$env_file" -y
  fi
  echo "Activating $PACKAGE_MANAGER environment: $KERNEL_NAME"
  _activate_env "$KERNEL_NAME"
fi
# set +u stays active for the remaining package-manager operations below;
# restored at the very end of the script.
_ensure_env_active

# A partial/interrupted env create leaves a named env that later runs skip
# recreating. Verify a few environment.yml packages; if missing, sync from the
# yaml (heal in place). Catches the gap before pip/editable installs paper over it.
_ensure_env_complete() {
  local py miss mod
  py="$(_env_python)"
  miss=()
  for mod in pydantic jupyter_client ipykernel pandas; do
    if ! "$py" -c "import ${mod}" >/dev/null 2>&1; then
      miss+=("$mod")
    fi
  done
  if ((${#miss[@]} == 0)); then
    return 0
  fi

  echo ""
  echo "Environment '$KERNEL_NAME' is incomplete (cannot import: ${miss[*]})."
  echo "This usually means a previous env create was interrupted; syncing from ${env_file}..."
  if [[ "$PACKAGE_MANAGER" == "micromamba" ]]; then
    if [[ -n "${CONDA_PREFIX:-}" ]]; then
      "$MICROMAMBA_CMD" install -y -p "$CONDA_PREFIX" -f "$env_file"
    else
      "$MICROMAMBA_CMD" install -y -n "$KERNEL_NAME" -f "$env_file"
    fi
  else
    "$CONDA_LIKE_CMD" env update -n "$KERNEL_NAME" -f "$env_file"
  fi

  miss=()
  for mod in pydantic jupyter_client ipykernel pandas; do
    if ! "$py" -c "import ${mod}" >/dev/null 2>&1; then
      miss+=("$mod")
    fi
  done
  if ((${#miss[@]} > 0)); then
    echo "Error: environment still incomplete after sync (missing: ${miss[*]})." >&2
    echo "  Remove and rebuild with: $0 --clean --batch" >&2
    exit 1
  fi
  echo "✓ Environment dependencies synced from ${env_file}."
}
_ensure_env_complete

# C-Star ships .env files for generic linux_* platforms but (as of main) no matching
# .lmod stubs. On HPC hosts where Lmod is present, import-time CStarSystemManager
# looks for <system_name>.lmod and FileNotFoundErrors. Empty stubs mean "load nothing".
_ensure_cstar_generic_lmod_stubs() {
  local py root stub name
  py="$(_env_python)"
  root="$("$py" -c "import cstar, pathlib; print(pathlib.Path(cstar.__file__).resolve().parent / 'additional_files' / 'lmod_lists')" 2>/dev/null || true)"
  if [[ -z "$root" || ! -d "$root" ]]; then
    echo "  Warning: could not locate cstar/additional_files/lmod_lists; skipping lmod stubs."
    return 0
  fi
  for name in linux_x86_64 linux_aarch64; do
    stub="$root/${name}.lmod"
    if [[ ! -f "$stub" ]]; then
      : > "$stub"
      echo "  Created empty C-Star lmod stub: $stub"
    fi
  done
}

#--------------------------------------------------------
# Optional compiler/library install (compilers, mpich, netcdf-fortran)
#--------------------------------------------------------
INSTALL_FORTRAN_LIBS="false"
if [[ "$WITH_COMPILERS" == "true" ]]; then
  INSTALL_FORTRAN_LIBS="true"
elif [[ "$BATCH_MODE" == "true" ]]; then
  echo "Batch mode enabled: skipping interactive compiler/library install prompt."
  echo "To install compilers/libraries later, run:"
  echo "  ${CONDA_LIKE_CMD} install -y -c conda-forge 'compilers<2' mpich netcdf-fortran"
else
  echo ""
  echo "C-Star Forge requires a FORTRAN compiler and supporting libraries (netcdf, MPI)."
  echo "This script can install them in the python environment, however they may conflict with compilers and libraries already installed locally."
  read -r -p 'Please indicate whether to install compilers and fortran libraries [y/N]: ' install_choice
  if [[ "$install_choice" =~ ^[Yy]$ ]]; then
    INSTALL_FORTRAN_LIBS="true"
  fi
fi

if [[ "$INSTALL_FORTRAN_LIBS" == "true" ]]; then
  echo "Installing compilers and library packages from conda-forge..."
  # compilers<2: metapackage 2.0.0 drops the triplet clang wrapper that
  # conda-forge mpich's mpicc hardcodes (broken mpicc on fresh osx-arm64 envs);
  # unpin once mpich is rebuilt against the new compilers
  if [[ "$PACKAGE_MANAGER" == "micromamba" ]]; then
    micromamba install -y -c conda-forge 'compilers<2' mpich netcdf-fortran
  else
    "$CONDA_LIKE_CMD" install -y -c conda-forge 'compilers<2' mpich netcdf-fortran
  fi
  echo "✓ Compiler installation completed successfully!"
else
  echo "Skipping compiler/library installation."
fi

#--------------------------------------------------------
# Pip install roms-tools and C-Star from GitHub (not in environment.yml)
#--------------------------------------------------------
_ensure_env_active

echo "Installing cstar-ocean and roms-tools from GitHub via pip (--no-deps)..."
echo "  All dependencies come from conda-forge (environment.yml); pip installs only"
echo "  the package code, never resolving or replacing the conda dependency tree."
_ensure_env_pip
# C-Star first; --no-deps means its (possibly stale) roms-tools pin is NOT enforced,
# so pip will not downgrade/replace the roms-tools we install next.
echo "  C-Star @ ${C_STAR_GIT_REF} (--no-deps)"
"$(_env_python)" -m pip install --no-deps --force-reinstall "git+https://github.com/CWorthy-ocean/C-Star.git@${C_STAR_GIT_REF}"
# roms-tools last so the requested ref is the final resident, overwriting the
# conda-forge package that was installed only to source dependencies.
echo "  roms-tools @ ${ROMS_TOOLS_GIT_REF} (--no-deps, installed last so it wins)"
"$(_env_python)" -m pip install --no-deps --force-reinstall "git+https://github.com/CWorthy-ocean/roms-tools.git@${ROMS_TOOLS_GIT_REF}"
echo "✓ roms-tools and C-Star pip installs completed."
# C-Star just landed in site-packages; make sure its generic .lmod stubs exist
# before anything imports cstar (see _ensure_cstar_generic_lmod_stubs above).
_ensure_cstar_generic_lmod_stubs

#--------------------------------------------------------
# Local package (editable) + Jupyter kernel
#--------------------------------------------------------
_ensure_env_active

echo "Installing cstar-forge in editable mode..."
cd "$SCRIPT_DIR"
# --no-deps: cstar-forge depends on cstar-ocean, which pins roms_tools<4. Without
# --no-deps, pip would re-resolve that chain and DOWNGRADE the roms-tools git build
# just installed above. All deps come from conda-forge (environment.yml) plus the
# --no-deps git installs above, so installing code-only is correct here.
"$(_env_python)" -m pip install -e . --no-deps
if import_err="$("$(_env_python)" -c "import cstar_forge" 2>&1)"; then
  echo "  ✓ cstar-forge installed successfully"
else
  echo "  ✗ cstar-forge installation failed (cannot import cstar_forge)"
  echo "    $import_err"
  if [[ "$import_err" == *".lmod"* ]]; then
    echo "  Hint: C-Star expected a missing generic .lmod stub; re-run setup or touch"
    echo "    \$CONDA_PREFIX/lib/python*/site-packages/cstar/additional_files/lmod_lists/linux_x86_64.lmod"
  else
    echo "  Hint: if conda deps are missing, try: $0 --clean --batch"
  fi
  exit 1
fi

_ensure_env_active
ENV_PREFIX="$("$(_env_python)" -c 'import sys; print(sys.prefix)')"
_install_pythonnousersite_hooks "$ENV_PREFIX"
export ENV_PREFIX

# Register the Jupyter kernel (+ activation wrapper) through the CLI the
# just-installed package ships: `cstar forge register-kernel`
# (cstar_forge/register_kernel.py). Installed users run the same command.
_register_kernel_args=(register-kernel --name "$KERNEL_NAME" --package-manager "$PACKAGE_MANAGER")
if [[ "$CLEAN_MODE" == "true" ]]; then
  _register_kernel_args+=(--clean)
fi
if [[ -n "${MICROMAMBA_CMD:-}" ]]; then
  _register_kernel_args+=(--micromamba-bin "$MICROMAMBA_CMD")
fi
"$(_env_python)" -m cstar_forge.cli "${_register_kernel_args[@]}"

#--------------------------------------------------------
# Verify installation (advisory only — never fatal)
#--------------------------------------------------------
echo ""
echo "Verifying installation (warnings only)..."
python - <<'PY' || true
import importlib.metadata as m

def _ver(dist):
    try:
        return m.version(dist)
    except Exception:
        return "(not found)"

print(f"  roms-tools : {_ver('roms-tools')}")
print(f"  cstar-ocean: {_ver('cstar-ocean')}")
try:
    import roms_tools  # noqa: F401
    import cstar  # noqa: F401
    print("  ✓ roms_tools and cstar import cleanly")
except Exception as e:
    print(f"  ⚠ import smoke test failed: {e!r}")
    print("    (roms-tools 4.x removed some APIs; C-Star may need an update to match.)")
PY

echo "Running 'pip check' (advisory)..."
echo "  A 'cstar-ocean requires roms-tools<4' style complaint is expected while"
echo "  C-Star's pin lags roms-tools main; it is not fatal."
_pip check || echo "  ⚠ pip check reported inconsistencies (see above) — not fatal."

echo ""
echo "✓ Environment setup completed successfully!"
echo "  Package manager: $PACKAGE_MANAGER"
echo "  Environment: $KERNEL_NAME"

#--------------------------------------------------------
# Local micromamba convenience messaging (only when local binary is used)
#--------------------------------------------------------
MICROMAMBA_PATH_SH="$LOCAL_BIN_DIR/micromamba-path.sh"
if [[ "$PACKAGE_MANAGER" == "micromamba" && "$MICROMAMBA_CMD" != "micromamba" && -x "$LOCAL_MICROMAMBA" ]]; then
  MAMBA_ROOT_PREFIX_EFFECTIVE="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
  cat > "$MICROMAMBA_PATH_SH" <<EOF
# Generated by dev-setup.sh — do not edit by hand (regenerated on each setup).
export PATH="${LOCAL_BIN_DIR}:\${PATH}"
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX_EFFECTIVE}"
EOF
  chmod a+r "$MICROMAMBA_PATH_SH"

  USER_LOCAL_BIN="${HOME}/.local/bin"
  if mkdir -p "$USER_LOCAL_BIN" 2>/dev/null && ln -sf "$LOCAL_MICROMAMBA" "$USER_LOCAL_BIN/micromamba" 2>/dev/null; then
    echo "micromamba symlink: $USER_LOCAL_BIN/micromamba"
    echo "  (Works in new terminals if $USER_LOCAL_BIN is on your PATH; many setups add it by default.)"
  fi
  echo "micromamba is installed at: $LOCAL_MICROMAMBA"
  if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    echo "This script was sourced: ./bin is already on PATH for this shell; run: micromamba --help"
  else
    echo "This script was run as a subprocess; your current shell PATH was not changed."
    echo "  In this terminal, run once: source \"$MICROMAMBA_PATH_SH\""
  fi
  echo ""
fi

echo "In a new terminal, activate by name with:"
if [[ "$PACKAGE_MANAGER" == "micromamba" ]]; then
  if [[ -f "$MICROMAMBA_PATH_SH" ]]; then
    echo "  source \"$MICROMAMBA_PATH_SH\""
  fi
  echo "  eval \"\$(micromamba shell hook -s bash)\"   # or: -s zsh / -s fish"
  echo "  micromamba activate $KERNEL_NAME"
elif [[ "$PACKAGE_MANAGER" == "mamba" ]]; then
  echo "  eval \"\$(mamba shell hook --shell bash)\"   # or: --shell zsh / --shell fish"
  echo "  mamba activate $KERNEL_NAME"
else
  echo "  source \"\$(conda info --base)/etc/profile.d/conda.sh\""
  echo "  conda activate $KERNEL_NAME"
fi
echo ""

set -u  # restore strict variable checking now that all conda operations are complete
