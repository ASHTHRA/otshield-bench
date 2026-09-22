#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"

BRANCH="automation/agent-loop"
LOCAL_MODEL="${LOCAL_MODEL:-qwen2.5-coder:3b}"
LOCAL_RETRIES="${LOCAL_RETRIES:-2}"
USE_CLOUD_FALLBACK="${USE_CLOUD_FALLBACK:-1}"
AUTO_PUSH="${AUTO_PUSH:-1}"

git switch "$BRANCH" >/dev/null
mkdir -p automation/status

verify_repo() {
  local out="$1"
  set +e
  python -m pytest -q >"$out" 2>&1
  local t=$?
  python -m build >>"$out" 2>&1
  local b=$?
  set -e
  [[ $t -eq 0 && $b -eq 0 ]]
}

restore() {
  git reset --hard "$1" >/dev/null
  git clean -fd     -e .venv/ -e captures/ -e dist/     -e automation/status/     -e 'otshield_*install*.sh'     -e 'otshield_multiengine*.sh' >/dev/null
}

make_prompt() {
  local task="$1"
  local extra="${2:-}"
  printf '%s\n\nTASK:\n%s\n\n%s\n'     "$(cat automation/AGENT_GUARDRAILS.md)"     "$(cat "$task")"     "Inspect first. Make the smallest truthful change. Add tests when behavior changes. Do not commit/push/merge/release. Never fabricate runtime validation. $extra"
}

run_local() {
  local prompt="$1"
  echo "LOCAL: Codex CLI -> Ollama/$LOCAL_MODEL"
  codex exec --oss --local-provider ollama -m "$LOCAL_MODEL"     --sandbox workspace-write "$prompt"
}

run_cloud() {
  local prompt="$1"
  echo "CLOUD ESCALATION: Codex/ChatGPT allowance"
  codex exec --sandbox workspace-write "$prompt"
}

commit_green() {
  local task="$1"
  local engine="$2"
  touch "${task}.done"
  rm -f "${task}.blocked"
  git add -A

  if git diff --cached --name-only | grep -E '(^|/)(\.env|captures/|\.venv/|dist/|build/)' >/dev/null; then
    git reset
    return 1
  fi

  git diff --cached --quiet ||     git commit -m "agent: $(basename "$task" .md | tr '_' ' ') [$engine]"

  [[ "$AUTO_PUSH" == "1" ]] && git push -u origin "$BRANCH" || true
}

record_blocker() {
  local task="$1"
  local log="$2"
  local f="automation/status/$(basename "$task" .md).blocked.md"
  {
    echo "# Blocked: $(basename "$task")"
    echo
    echo "No attempted implementation passed tests + build."
    echo "The repository was restored to the last green commit."
    echo
    echo ''
  } >"$f"
  touch "${task}.blocked"
  git add "$f" "${task}.blocked"
  git commit -m "chore: record blocked task $(basename "$task")" || true
  [[ "$AUTO_PUSH" == "1" ]] && git push -u origin "$BRANCH" || true
}

mapfile -t TASKS < <(find automation/tasks -maxdepth 1 -name '*.md' | sort)

for task in "${TASKS[@]}"; do
  [[ -f "${task}.done" ]] && continue

  echo
  echo "===== $task ====="
  base="$(git rev-parse HEAD)"
  log="/tmp/otshield_verify.log"
  success=0

  # Free local attempts first
  for n in $(seq 1 "$LOCAL_RETRIES"); do
    restore "$base"
    extra=""
    [[ $n -gt 1 && -f "$log" ]] && extra="Previous verification failed: $(tail -n 60 "$log")"

    set +e
    run_local "$(make_prompt "$task" "$extra")"
    rc=$?
    set -e

    if [[ $rc -eq 0 ]] && verify_repo "$log"; then
      commit_green "$task" "local:$LOCAL_MODEL"
      success=1
      break
    fi
  done

  [[ $success -eq 1 ]] && continue

  # Optional cloud escalation. Quota/auth failure does NOT stop the queue.
  if [[ "$USE_CLOUD_FALLBACK" == "1" ]] && codex login status >/dev/null 2>&1; then
    restore "$base"
    set +e
    run_cloud "$(make_prompt "$task" "Local attempts failed. Diagnose carefully. Do not weaken tests.")"
    rc=$?
    set -e

    if [[ $rc -eq 0 ]] && verify_repo "$log"; then
      commit_green "$task" "cloud"
      success=1
    fi
  fi

  [[ $success -eq 1 ]] && continue

  # Never kill the whole queue because one task failed.
  restore "$base"
  record_blocker "$task" "$log"
  echo "Marked blocked; continuing to next task."
done

echo
echo "== Queue finished =="
echo "Local model: $LOCAL_MODEL"
echo "Completed:"
find automation/tasks -name '*.done' -printf '  %f\n' | sort || true
echo "Blocked:"
find automation/tasks -name '*.blocked' -printf '  %f\n' | sort || true
python -m pytest -q || true
