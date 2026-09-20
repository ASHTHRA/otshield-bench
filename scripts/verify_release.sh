#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "===== OTSHIELD RELEASE VERIFICATION ====="
echo "Commit: $(git rev-parse HEAD)"
python --version

echo
echo "[1/3] git diff --check"
git diff --check

echo
echo "[2/3] full test suite"
python -m pytest -q

echo
echo "[3/3] package build"
python -m build

echo
echo "===== RELEASE VERIFICATION PASSED ====="
