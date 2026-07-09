#!/usr/bin/env bash
# Launch the ForgeBlueprint builder as a standalone Voilà web app (code hidden).
#
# Local laptop:
#   ./examples/run-wizard-app.sh
#   -> opens http://localhost:8866 in your browser
#
# HPC login node (no browser there): run it bound to localhost, then SSH
# port-forward from your laptop:
#   # on the login node:
#   ./examples/run-wizard-app.sh --no-browser
#   # on your laptop:
#   ssh -N -L 8866:localhost:8866 <user>@<login-node>
#   # then open http://localhost:8866 locally
#
# Requires: voila (pip install voila) in the active environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec voila "${HERE}/forge-blueprint-wizard-app.ipynb" \
  --port=8866 \
  --Voila.tornado_settings='{"allow_origin": "*"}' \
  "$@"
