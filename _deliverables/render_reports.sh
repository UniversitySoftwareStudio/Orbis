#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/01_Report1/render.sh"
"$SCRIPT_DIR/02_Report2/render.sh"
