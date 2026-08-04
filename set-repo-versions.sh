#!/bin/bash
# Install custom versions of roms-tools and C-Star into the current
# (already-active) environment.
#
# Usage:
#   ./set-repo-versions.sh                                     # interactive prompts
#   ./set-repo-versions.sh --roms-tools-ref abc1234             # non-interactive
#   ./set-repo-versions.sh --c-star-ref=main
#   ./set-repo-versions.sh --roms-tools-ref abc1234 --c-star-ref main
#
# For each repo, pass a branch name, tag, or commit hash to install that ref via
# `pip install --no-deps git+https://github.com/CWorthy-ocean/<repo>.git@<ref>`.
# Refs are only prompted for interactively when the corresponding flag is
# omitted; leaving an interactive prompt blank (default "none") skips that repo.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/harden-env.sh
source "$SCRIPT_DIR/scripts/harden-env.sh"
_assert_env_active

NOOP_PLACEHOLDER="none"
ROMS_TOOLS_GIT_REF=""
C_STAR_GIT_REF=""

while [[ $# -gt 0 ]]; do
  case "$1" in
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
      echo "Usage: $0 [--roms-tools-ref REF] [--c-star-ref REF]" >&2
      exit 1 ;;
  esac
done

prompt_ref() {
  local prompt_label="$1"
  local input
  read -r -p "${prompt_label} [default: ${NOOP_PLACEHOLDER} = skip]: " input
  if [[ -z "$input" ]]; then
    input="$NOOP_PLACEHOLDER"
  fi
  echo "$input"
}

install_pip_repo() {
  local repo_name="$1"
  local ref="$2"
  if [[ -z "$ref" || "$ref" == "$NOOP_PLACEHOLDER" ]]; then
    echo "Skipping ${repo_name} (no ref provided)."
    return
  fi
  echo "Installing ${repo_name} @ ${ref} (--no-deps)..."
  python -m pip install --no-deps "git+https://github.com/CWorthy-ocean/${repo_name}.git@${ref}"
}

# Only prompt for a repo whose ref wasn't already supplied via flag.
if [[ -z "$ROMS_TOOLS_GIT_REF" ]]; then
  ROMS_TOOLS_GIT_REF=$(prompt_ref "roms-tools ref (branch/commit/tag)")
fi
if [[ -z "$C_STAR_GIT_REF" ]]; then
  C_STAR_GIT_REF=$(prompt_ref "C-Star ref (branch/commit/tag)")
fi

install_pip_repo "roms-tools" "$ROMS_TOOLS_GIT_REF"
install_pip_repo "C-Star" "$C_STAR_GIT_REF"

echo "Done."
