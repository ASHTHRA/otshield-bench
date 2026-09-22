#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"

BRANCH="automation/agent-loop"
LOCAL_MODEL="${LOCAL_MODEL:-qwen2.5-coder:3b}"
LOCAL_RETRIES="${LOCAL_RETRIES:-3}"
USE_CLOUD_FALLBACK="${USE_CLOUD_FALLBACK:-1}"
AUTO_PUSH="${AUTO_PUSH:-1}"

git switch "$BRANCH" >/dev/null
mkdir -p automation/status

count_tests() {
  python -m pytest --collect-only -q 2>/dev/null | tail -n 1 | grep -oE '[0-9]+ test' | grep -oE '[0-9]+' || echo 0
}

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
  git clean -fd \
    -e .venv/ -e captures/ -e dist/ \
    -e automation/status/ \
    -e 'otshield_*install*.sh' \
    -e 'otshield_multiengine*.sh' \
    -e 'otshield_strict*.sh' >/dev/null
}

changed_real_files() {
  git status --porcelain | awk '{print $2}' \
    | grep -vE '^automation/tasks/.*\.(done|blocked)$' \
    | grep -vE '^automation/status/' || true
}

acceptance_check() {
  local task="$1"
  local before_tests="$2"
  local after_tests="$3"
  local files
  files="$(changed_real_files)"

  [[ -n "$files" ]] || {
    echo "REJECT: agent made no substantive repository changes."
    return 1
  }

  case "$(basename "$task")" in
    01_ground_truth_protocol.md)
      echo "$files" | grep -q '^src/otshield/' || { echo "REJECT: no src/otshield source change"; return 1; }
      echo "$files" | grep -q '^tests/' || { echo "REJECT: no test change"; return 1; }
      (( after_tests > before_tests )) || { echo "REJECT: test count did not increase"; return 1; }
      ;;
    02_pcap_transaction_correlation.md)
      echo "$files" | grep -Eq '^(src/otshield/|scripts/)' || { echo "REJECT: no implementation change"; return 1; }
      echo "$files" | grep -q '^tests/' || { echo "REJECT: no test change"; return 1; }
      (( after_tests > before_tests )) || { echo "REJECT: test count did not increase"; return 1; }
      ;;
    03_simulation_adapter.md)
      echo "$files" | grep -Eq '^(src/otshield/|scripts/|docker/)' || { echo "REJECT: no simulation/preflight implementation change"; return 1; }
      echo "$files" | grep -q '^tests/' || { echo "REJECT: no test change"; return 1; }
      (( after_tests > before_tests )) || { echo "REJECT: test count did not increase"; return 1; }
      ;;
    04_results_manifest.md)
      echo "$files" | grep -q '^src/otshield/' || { echo "REJECT: no src/otshield implementation change"; return 1; }
      echo "$files" | grep -q '^tests/' || { echo "REJECT: no test change"; return 1; }
      (( after_tests > before_tests )) || { echo "REJECT: test count did not increase"; return 1; }
      ;;
    05_reproducibility_release.md)
      echo "$files" | grep -Eq '^(docs/|README\.md$|scripts/|\.github/)' || {
        echo "REJECT: no reproducibility/docs/script change"
        return 1
      }
      ;;
  esac

  # Require a minimum substantive diff for engineering tasks.
  if [[ "$(basename "$task")" != "05_reproducibility_release.md" ]]; then
    local changed_lines
    changed_lines="$(git diff --numstat | awk '{a+=$1; d+=$2} END {print a+d+0}')"
    (( changed_lines >= 12 )) || {
      echo "REJECT: substantive diff too small ($changed_lines changed lines)"
      return 1
    }
  fi

  return 0
}

make_prompt() {
  local task="$1"
  local feedback="${2:-}"
  cat <<PROMPT
$(cat automation/AGENT_GUARDRAILS.md)

TASK:
$(cat "$task")

STRICT COMPLETION RULES:
- You MUST make substantive repository changes for this task.
- Do not merely explain, inspect, or say the feature already exists.
- Do not create .done/.blocked marker files.
- For Tasks 01-04, implement behavior AND add new tests.
- Existing tests passing is not sufficient; the task-specific capability must be implemented and tested.
- Keep changes small, deterministic, defensive, and truthful.
- Do not commit, push, tag, merge, or release.
- Never fabricate GRFICS/Docker/PCAP runtime evidence.

$feedback
PROMPT
}

run_local() {
  local prompt="$1"
  local prompt_file
  prompt_file="$(mktemp /tmp/otshield-aider-prompt.XXXXXX)"
  printf '%s
' "$prompt" >"$prompt_file"

  echo "LOCAL EDIT ENGINE: Aider -> Ollama/$LOCAL_MODEL"

  set +e
  OLLAMA_API_BASE="http://127.0.0.1:11434"   AIDER_CHAT_HISTORY_FILE="/tmp/otshield-aider-chat-history.md"   AIDER_INPUT_HISTORY_FILE="/tmp/otshield-aider-input-history"   aider     --model "ollama_chat/$LOCAL_MODEL"     --model-settings-file "$HOME/.aider.model.settings.yml"     --edit-format whole     --message-file "$prompt_file"     --yes-always     --no-auto-commits     --no-dirty-commits     --no-gitignore     --no-auto-lint     --no-auto-test     --no-check-update     --no-show-release-notes     --no-show-model-warnings     --no-stream
  local rc=$?
  set -e

  rm -f "$prompt_file"
  return "$rc"
}

run_cloud() {
  local prompt="$1"
  codex exec --sandbox workspace-write "$prompt"
}

finish_task() {
  local task="$1"
  local engine="$2"

  touch "${task}.done"
  rm -f "${task}.blocked"

  git add -A

  if git diff --cached --name-only | grep -E '(^|/)(\.env|captures/|\.venv/|dist/|build/)' >/dev/null; then
    echo "Unsafe/generated content detected; rejecting."
    git reset
    return 1
  fi

  git commit -m "agent: verified $(basename "$task" .md | tr '_' ' ') [$engine]"
  [[ "$AUTO_PUSH" == "1" ]] && git push -u origin "$BRANCH" || true
}

record_blocker() {
  local task="$1"
  local msg="$2"
  local f="automation/status/$(basename "$task" .md).blocked.md"

  {
    echo "# Blocked: $(basename "$task")"
    echo
    echo "$msg"
    echo
    echo "The task was not marked complete."
  } >"$f"

  touch "${task}.blocked"
  git add "$f" "${task}.blocked"
  git commit -m "chore: strict verifier blocked $(basename "$task")" || true
  [[ "$AUTO_PUSH" == "1" ]] && git push -u origin "$BRANCH" || true
}

mapfile -t TASKS < <(find automation/tasks -maxdepth 1 -type f \
  \( -name '01_*.md' -o -name '02_*.md' -o -name '03_*.md' -o -name '04_*.md' -o -name '05_*.md' \) | sort)

for task in "${TASKS[@]}"; do
  [[ -f "${task}.done" ]] && continue

  echo
  echo "============================================================"
  echo "STRICT TASK: $task"
  echo "============================================================"

  base="$(git rev-parse HEAD)"
  before_tests="$(count_tests)"
  feedback=""
  success=0

  for attempt in $(seq 1 "$LOCAL_RETRIES"); do
    restore "$base"

    echo "Local strict attempt $attempt/$LOCAL_RETRIES..."
    set +e
    run_local "$(make_prompt "$task" "$feedback")"
    rc=$?
    set -e

    after_tests="$(count_tests)"

    if [[ $rc -eq 0 ]] && acceptance_check "$task" "$before_tests" "$after_tests"; then
      if verify_repo "/tmp/otshield_strict_verify.log"; then
        finish_task "$task" "local:$LOCAL_MODEL"
        success=1
        break
      fi
      feedback="Previous implementation changed files but failed full pytest/build. Fix it without weakening tests. Tail:
$(tail -n 80 /tmp/otshield_strict_verify.log 2>/dev/null || true)"
    else
      feedback="Previous attempt was rejected by strict acceptance. You must actually implement the requested feature and add tests. Current rejection means no substantive verified feature was produced."
    fi
  done

  [[ $success -eq 1 ]] && continue

  # Optional cloud escalation, never mandatory for queue safety.
  if [[ "$USE_CLOUD_FALLBACK" == "1" ]] && codex login status >/dev/null 2>&1; then
    restore "$base"
    echo "Trying cloud escalation once..."
    set +e
    run_cloud "$(make_prompt "$task" "$feedback")"
    rc=$?
    set -e
    after_tests="$(count_tests)"

    if [[ $rc -eq 0 ]] && acceptance_check "$task" "$before_tests" "$after_tests" \
       && verify_repo "/tmp/otshield_strict_verify.log"; then
      finish_task "$task" "cloud"
      success=1
    fi
  fi

  [[ $success -eq 1 ]] && continue

  restore "$base"
  record_blocker "$task" "Three local attempts plus any available cloud fallback failed the strict completion criteria."
  echo "Task remains BLOCKED, not falsely DONE."
done

echo
echo "== STRICT QUEUE FINISHED =="
echo "Completed:"
find automation/tasks -maxdepth 1 -name '*.done' -printf '  %f\n' | sort
echo "Blocked:"
find automation/tasks -maxdepth 1 -name '*.blocked' -printf '  %f\n' | sort
echo
echo "Final tests:"
python -m pytest -q
