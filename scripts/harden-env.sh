#!/bin/bash
# scripts/harden-env.sh
#
# Sourced by dev-setup.sh and set-repo-versions.sh. Keeps pip/python
# operations locked onto the intended conda/micromamba environment and off
# ~/.local, which is what actually breaks HPC installs (Anvil et al.) when it
# goes unnoticed: pip's --user fallback (~/.local/lib/pythonX.Y) detaches
# packages from the conda env, then shadows it via user-site on the next run
# (env python and a module/system python of the same minor version share
# ~/.local).
#
# Provides:
#   _activate_env <name>              activate via $CONDA_LIKE_CMD, falling
#                                      back to plain conda if that fails
#   _assert_env_active                 hard-fail unless the active python is
#                                      the target env (matches $KERNEL_NAME if
#                                      set, else requires any non-base env)
#   _ensure_env_active                 (re)activate the env, then assert
#   _env_python                        print the env's own python path
#                                      ($CONDA_PREFIX/bin/python), so HPC module
#                                      pythons can't shadow it
#   _ensure_env_pip                    verify `<env python> -m pip` works,
#                                      bootstrapping via ensurepip if missing
#   _install_pythonnousersite_hooks <env_prefix>
#                                      persist PYTHONNOUSERSITE=1 into the env
#                                      itself via an activate.d/deactivate.d
#                                      hook, so it survives future activations
#
# Callers set the following before relying on the functions above:
#   KERNEL_NAME     target env name (dev-setup.sh; leave unset for the looser
#                   set-repo-versions.sh check)
#   CONDA_LIKE_CMD  "conda" or "mamba" (used by _activate_env)
#   PACKAGE_MANAGER "micromamba" or the conda-like tool (used by _ensure_env_active)
#   MICROMAMBA_CMD  path/name of the micromamba binary in use

# PIP_USER=0 forbids the --user fallback outright; PYTHONNOUSERSITE=1 keeps
# every python we launch here (checks, ipykernel, pip) from reading ~/.local
# at all.
export PIP_USER=0
export PYTHONNOUSERSITE=1

_activate_env() {
  local env_name="$1"
  # Primary attempt (mamba or conda)
  $CONDA_LIKE_CMD activate "$env_name" 2>/dev/null || true
  if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
    return 0
  fi
  # Fall back to conda when the primary tool (mamba) failed to activate
  if [[ "${CONDA_LIKE_CMD:-conda}" != "conda" ]]; then
    echo "  Warning: '$CONDA_LIKE_CMD activate' did not activate '$env_name'; falling back to 'conda activate'..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$env_name" 2>/dev/null || true
    if [[ "${CONDA_DEFAULT_ENV:-}" == "$env_name" ]]; then
      return 0
    fi
  fi
  echo "Error: Could not activate environment '$env_name' via $CONDA_LIKE_CMD or conda." >&2
  exit 1
}

# Hard-verify that `python`/`pip` now resolve INTO the target env, not a stray
# module/system python. Without this, a silently-failed activation leaves pip
# pointed at a read-only system site-packages, and pip installs into ~/.local.
# When KERNEL_NAME is set (dev-setup.sh), require an exact match (the env is
# created by name, so it lives at <root>/envs/$KERNEL_NAME and its
# sys.prefix basename is $KERNEL_NAME). When unset (set-repo-versions.sh,
# which operates on "whatever env the caller already activated"), just
# require some non-base env to be active.
_assert_env_active() {
  local prefix
  prefix="$(python -c 'import sys; print(sys.prefix)' 2>/dev/null || true)"
  if [[ -n "${KERNEL_NAME:-}" ]]; then
    if [[ "$(basename "$prefix")" != "$KERNEL_NAME" ]]; then
      echo "Error: environment '$KERNEL_NAME' is not active (active python prefix: ${prefix:-<none>})." >&2
      echo "  Refusing to run pip/python against a non-env interpreter — it would install into ~/.local" >&2
      echo "  and become detached from the conda environment. Re-run from a shell where the package" >&2
      echo "  manager is initialized (micromamba/conda shell hook)." >&2
      exit 1
    fi
  elif [[ -z "${CONDA_DEFAULT_ENV:-}" ]] || [[ "${CONDA_DEFAULT_ENV}" == "base" ]]; then
    echo "Error: no non-base conda/micromamba environment is active." >&2
    echo "  Activate the project env first (e.g. 'micromamba activate cstar-forge-env')," >&2
    echo "  then re-run this script. Installing now would land in ~/.local, detached from the env." >&2
    exit 1
  fi
}

# Re-activate the env if it isn't already the active one, then assert the active
# python really is the env's. Replaces the previously-duplicated (and, for
# micromamba, unverified) "ensure environment is active" blocks.
_ensure_env_active() {
  if [[ -z "${CONDA_DEFAULT_ENV:-}" ]] || [[ "$CONDA_DEFAULT_ENV" != "${KERNEL_NAME:-}" ]]; then
    if [[ "${PACKAGE_MANAGER:-}" == "micromamba" ]]; then
      # Shell hook (eval'd earlier) provides the `micromamba` function; keep the
      # alias for local-binary parity even though it is inert non-interactively.
      if [[ "${MICROMAMBA_CMD:-micromamba}" != "micromamba" ]]; then
        alias micromamba="$MICROMAMBA_CMD"
      fi
      micromamba activate "$KERNEL_NAME"
    else
      source "$(conda info --base)/etc/profile.d/conda.sh"
      _activate_env "$KERNEL_NAME"
    fi
  fi
  _assert_env_active
}

# Prefer "$CONDA_PREFIX/bin/python -m pip" so HPC module Pythons (e.g. EasyBuild
# Python/*/bin/pip) cannot shadow a missing/broken env pip and cause:
#   ModuleNotFoundError: No module named 'pip'
_env_python() {
  if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    echo "${CONDA_PREFIX}/bin/python"
  else
    command -v python
  fi
}

_ensure_env_pip() {
  local py
  py="$(_env_python)"
  if ! "$py" -m pip --version >/dev/null 2>&1; then
    echo "  pip not found in active env; bootstrapping with ensurepip..."
    "$py" -m ensurepip --upgrade
  fi
  if ! "$py" -m pip --version >/dev/null 2>&1; then
    echo "Error: Could not import pip for: $py" >&2
    echo "  CONDA_PREFIX=${CONDA_PREFIX:-<unset>}" >&2
    echo "  which pip -> $(command -v pip 2>/dev/null || echo none)" >&2
    echo "  Install pip into the env (e.g. conda install -n ${KERNEL_NAME:-<env>} pip) and retry." >&2
    exit 1
  fi
  echo "  Using: $py -m pip ($("$py" -m pip --version))"
}

# Persist PYTHONNOUSERSITE=1 into the env itself via an activate.d hook, so every
# future activation (interactive shells, later runs, jupyter) keeps the env off
# user-site (~/.local). Conda/micromamba don't set this by default, so without it
# a ~/.local/lib/python3.12/site-packages dir (env python and Anvil's module
# python share the same 3.12 user-site) silently shadows the env's packages.
_install_pythonnousersite_hooks() {
  local env_prefix="$1"
  local activate_d_dir="$env_prefix/etc/conda/activate.d"
  local deactivate_d_dir="$env_prefix/etc/conda/deactivate.d"
  mkdir -p "$activate_d_dir" "$deactivate_d_dir"
  cat > "$activate_d_dir/pythonnousersite.sh" <<'EOF'
# Auto-generated by dev-setup.sh — keep this env isolated from ~/.local.
export _CSTAR_FORGE_SAVED_PYTHONNOUSERSITE="${PYTHONNOUSERSITE:-}"
export PYTHONNOUSERSITE=1
EOF
  cat > "$deactivate_d_dir/pythonnousersite.sh" <<'EOF'
# Auto-generated by dev-setup.sh — restore PYTHONNOUSERSITE on deactivate.
if [ -n "${_CSTAR_FORGE_SAVED_PYTHONNOUSERSITE:-}" ]; then
  export PYTHONNOUSERSITE="$_CSTAR_FORGE_SAVED_PYTHONNOUSERSITE"
else
  unset PYTHONNOUSERSITE
fi
unset _CSTAR_FORGE_SAVED_PYTHONNOUSERSITE
EOF
  echo "✓ Wrote activate.d/deactivate.d PYTHONNOUSERSITE hooks in $env_prefix"
}
