#!/bin/bash
# Interactively install custom versions of roms-tools and C-Star into the
# current (already-active) environment.
#
# Usage:
#   ./set-repo-versions.sh
#
# For each repo, enter a branch name, tag, or commit hash to install that ref
# via `pip install --no-deps git+https://github.com/CWorthy-ocean/<repo>.git@<ref>`.
# Leave the prompt blank (default "none") to skip that repo entirely.

set -e

NOOP_PLACEHOLDER="none"

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
  if [[ "$ref" == "$NOOP_PLACEHOLDER" ]]; then
    echo "Skipping ${repo_name} (no ref provided)."
    return
  fi
  echo "Installing ${repo_name} @ ${ref} (--no-deps)..."
  pip install --no-deps "git+https://github.com/CWorthy-ocean/${repo_name}.git@${ref}"
}

ROMS_TOOLS_REF=$(prompt_ref "roms-tools ref (branch/commit/tag)")
C_STAR_REF=$(prompt_ref "C-Star ref (branch/commit/tag)")

install_pip_repo "roms-tools" "$ROMS_TOOLS_REF"
install_pip_repo "C-Star" "$C_STAR_REF"

echo "Done."
