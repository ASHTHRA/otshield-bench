#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -x "$root/.venv/bin/python" ]]; then
  python_bin="$root/.venv/bin/python"
else
  python_bin="python"
fi
export PYTHONPATH="$root:$root/src"
exec "$python_bin" -m scripts.agent_runner "$@"
