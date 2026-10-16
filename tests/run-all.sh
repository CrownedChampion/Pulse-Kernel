#!/usr/bin/env bash
set -Eeuo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s "$R/tests" -p 'test_*.py' -v
"$R/tests/test_identity.sh"
python3 "$R/scripts/config-audit.py" "$R/config/debian-6.12.107-amd64-reference.config"
