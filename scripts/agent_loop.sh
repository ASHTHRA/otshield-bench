#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$ROOT" ]] || { echo "ERROR: run inside repo"; exit 1; }
cd "$ROOT"

MAX_ITERS="${MAX_ITERS:-10}"
AUTO_PUSH="${AUTO_PUSH:-1}"
BRANCH="${BRANCH:-automation/agent-loop}"
TASK_DIR="${TASK_DIR:-automation/tasks}"

source .venv/bin/activate

if ! command -v codex >/dev/null 2>&1; then
  echo "Installing official Codex CLI..."
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: Codex CLI still not available on PATH."
  exit 2
fi

# codex itself will initiate sign-in if needed.
if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  git switch "$BRANCH"
fi

mapfile -t TASKS < <(find "$TASK_DIR" -maxdepth 1 -type f -name '*.md' | sort)
iter=0

for task in "${TASKS[@]}"; do
  marker="${task}.done"
  [[ -f "$marker" ]] && continue

  ((iter+=1))
  if [[ "$MAX_ITERS" != "0" && "$iter" -gt "$MAX_ITERS" ]]; then
    break
  fi

  echo
  echo "===== Agent iteration $iter: $(basename "$task") ====="
  before="$(git rev-parse HEAD)"

  PROMPT="$(cat automation/AGENT_GUARDRAILS.md)

TASK:
$(cat "$task")

Execution requirements:
- Inspect the repository before editing.
- Implement the smallest complete change.
- Add/update tests when behavior changes.
- Run relevant tests yourself when possible.
- Do not commit, push, tag, merge, or release.
- Finish with files changed and blockers.
"

  set +e
  codex exec --sandbox workspace-write "$PROMPT"
  agent_rc=$?
  set -e

  if [[ $agent_rc -ne 0 ]]; then
    echo "Agent failed; restoring last green commit."
    git reset --hard "$before"
    git clean -fd -e .venv/ -e captures/ -e dist/
    exit 10
  fi

  echo "Running full verification..."
  set +e
  pytest -q
  test_rc=$?
  python -m build >/dev/null
  build_rc=$?
  set -e

  if [[ $test_rc -ne 0 || $build_rc -ne 0 ]]; then
    echo "Verification failed; restoring last green commit."
    git reset --hard "$before"
    git clean -fd -e .venv/ -e captures/ -e dist/
    exit 11
  fi

  if git status --porcelain | grep -E '(^.. )?(\.env|captures/|\.venv/|dist/|build/)' >/dev/null; then
    echo "Unsafe/generated file detected; restoring last green commit."
    git reset --hard "$before"
    git clean -fd -e .venv/ -e captures/ -e dist/
    exit 12
  fi

  touch "$marker"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    git commit -m "agent: $(basename "$task" .md | tr '_' ' ')"
  fi

  if [[ "$AUTO_PUSH" == "1" ]]; then
    git push -u origin "$BRANCH"
  fi
done

echo
echo "AUTONOMOUS LOOP COMPLETE"
git log -1 --oneline
echo "branch: $(git branch --show-current)"
pytest -q
