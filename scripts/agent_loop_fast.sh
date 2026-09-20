#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"
FAST_MODEL="${FAST_MODEL:-groq/openai/gpt-oss-20b}"
STRONG_MODEL="${STRONG_MODEL:-groq/openai/gpt-oss-120b}"
ONLY_TASK="${ONLY_TASK:-}"
VERIFY_LOG="/tmp/otshield_fast_verify.$$"
AIDER_LOG="/tmp/otshield_fast_aider.$$"

: "${GROQ_API_KEY:?GROQ_API_KEY is required}"
: "${TYPESAFE_API_KEY:?TYPESAFE_API_KEY is required}"

command -v aider >/dev/null 2>&1 || {
  echo "ERROR: aider is not installed" >&2
  exit 2
}

python -c 'import typesafe_sdk' >/dev/null 2>&1 || {
  echo "ERROR: typesafe-sdk is not installed in the active Python environment" >&2
  exit 2
}

count_tests(){
  local output count
  output="$(pytest --collect-only -q 2>/dev/null || true)"
  count="$(
    printf '%s\n' "$output" |
      sed -nE 's/^([0-9]+) tests? collected.*$/\1/p' |
      tail -n1
  )"
  [[ "$count" =~ ^[0-9]+$ ]] || count=0
  printf '%s\n' "$count"
}
verify_all(){
  {
    pytest -q &&
    python -m build
  } 2>&1 | tee "$VERIFY_LOG"
}
restore(){ git reset --hard "$1" >/dev/null; git clean -fd -e .venv/ -e captures/ -e dist/ -e 'otshield_*.sh' -e automation/status/ >/dev/null; }

jev_decision(){
  local task="$1"
  local phase="$2"
  local state_file
  local json_file
  local decision

  state_file="$(mktemp)"
  json_file="$(mktemp)"

  {
    echo "OTShield autonomous-agent state"
    echo
    echo "Phase: $phase"
    echo "Task: $(basename "$task")"
    echo
    echo "Task definition:"
    cat "$task"
    echo
    echo "Repository status:"
    git status --short || true
    echo
    echo "Current diff summary:"
    git diff --stat || true
    echo
    echo "Latest Aider output:"
    if [[ -s "$AIDER_LOG" ]]; then
      tail -n 80 "$AIDER_LOG"
    else
      echo "No Aider output was captured."
    fi
    echo
    echo "Latest verification output:"
    if [[ -s "$VERIFY_LOG" ]]; then
      tail -n 100 "$VERIFY_LOG"
    else
      echo "No verification output was produced."
    fi
  } >"$state_file"

  if decision="$(
    python scripts/jev_gate.py       --state-file "$state_file"       --json-out "$json_file"
  )"; then
    echo "JEV DECISION: $decision" >&2
    [[ -s "$json_file" ]] && cat "$json_file" >&2
  else
    echo "JEV API/controller failure: failing closed." >&2
    decision="human_review"
  fi

  rm -f "$state_file" "$json_file"
  printf '%s\n' "$decision"
}

prep_files(){
  case "$1" in
    01_ground_truth_protocol.md)
      touch src/otshield/ground_truth.py tests/test_ground_truth.py docs/ground-truth.md
      FILES=(src/otshield/ground_truth.py src/otshield/cli.py tests/test_ground_truth.py docs/ground-truth.md);;
    02_pcap_transaction_correlation.md)
      touch src/otshield/adapters/pcap.py tests/test_pcap.py docs/pcap-ingestion.md
      FILES=(src/otshield/adapters/pcap.py src/otshield/adapters/base.py src/otshield/adapters/model.py src/otshield/adapters/__init__.py src/otshield/cli.py tests/test_pcap.py tests/test_ingestion.py docs/pcap-ingestion.md pyproject.toml);;
    03_simulation_adapter.md)
      touch src/otshield/adapters/simulation.py tests/test_adapters.py
      FILES=(src/otshield/adapters/base.py src/otshield/adapters/simulation.py src/otshield/adapters/__init__.py tests/test_adapters.py docker/docker-compose.grfics.yml docs/grfics-integration.md);;
    04_results_manifest.md)
      touch src/otshield/results.py tests/test_results.py docs/results-manifest.md
      FILES=(src/otshield/results.py src/otshield/evaluation.py src/otshield/detectors.py src/otshield/core.py tests/test_results.py tests/test_bench.py docs/results-manifest.md);;
    05_reproducibility_release.md)
      touch scripts/verify_release.sh docs/reproducibility.md; chmod +x scripts/verify_release.sh
      FILES=(scripts/verify_release.sh docs/reproducibility.md README.md pyproject.toml);;
  esac
}

run_aider(){
  local model="$1" timeout_s="$2" fmt="$3" task="$4" pf; pf="$(mktemp)"
  cat >"$pf" <<PROMPT
$(cat automation/AGENT_GUARDRAILS.md)

TASK:
$(cat "$task")

FOCUSED MODE:
- Implement now; do not ask the user questions.
- Work only on the supplied files unless one tiny additional file is essential.
- Add focused tests for engineering tasks.
- Never create done/blocked markers.
- Never fabricate GRFICS/OpenPLC/PCAP execution, measurements, adoption, publication, or validation.
- Keep synthetic and lab-derived provenance distinct.
- Do not commit, push, merge, tag, or release.
PROMPT
  args=(); for f in "${FILES[@]}"; do args+=(--file "$f"); done
  set +e
  : >"$AIDER_LOG"
  rc=1

  for provider_attempt in 1 2; do
    echo "Groq attempt $provider_attempt/2: $model" | tee -a "$AIDER_LOG"

    timeout --signal=INT --kill-after=30s "${timeout_s}s" aider \
      --model "$model" \
      --model-settings-file automation/aider-groq-settings.yml \
      --edit-format "$fmt" --map-tokens 0 --max-chat-history-tokens 8192 \
      --message-file "$pf" --yes-always --no-auto-commits --no-dirty-commits \
      --no-auto-lint --no-auto-test --no-check-update --no-show-release-notes --no-stream \
      "${args[@]}" 2>&1 | tee -a "$AIDER_LOG"

    rc=${PIPESTATUS[0]}

    if [[ $rc -eq 0 ]]; then
      break
    fi

    if [[ $provider_attempt -eq 1 ]] &&
       grep -Eqi 'token limit|rate limit|too many requests|HTTP 429|429' "$AIDER_LOG"; then
      echo "Groq rate window exhausted; waiting 70 seconds before retry." |
        tee -a "$AIDER_LOG"
      sleep 70
      continue
    fi

    break
  done

  set -e
  rm -f "$pf"
  return $rc
}

accept(){
  local task="$1" before="$2" after="$3" files
  files="$(git status --porcelain | awk '{print $2}' | grep -vE '^automation/(tasks|status)/' || true)"
  [[ -n "$files" ]] || return 1
  case "$(basename "$task")" in
    01_*|02_*|03_*|04_*)
      echo "$files" | grep -q '^src/otshield/' || return 1
      echo "$files" | grep -q '^tests/' || return 1
      [[ "$before" =~ ^[0-9]+$ && "$after" =~ ^[0-9]+$ ]] || return 1
      (( 10#$after > 10#$before )) || return 1;;
    05_*) echo "$files" | grep -Eq '^(scripts/|docs/|README\.md)' || return 1;;
  esac
}

for task in automation/tasks/0{1,2,3,4,5}_*.md; do
  [[ -e "$task" ]] || continue

  if [[ -n "$ONLY_TASK" && "$(basename "$task")" != "$ONLY_TASK" ]]; then
    continue
  fi

  [[ -e "${task}.done" ]] && continue
  base="$(git rev-parse HEAD)"; before="$(count_tests)"; ok=0
  : >"$VERIFY_LOG"
  echo "===== FAST TASK: $(basename "$task") ====="

  restore "$base"; prep_files "$(basename "$task")"
  echo "FAST PASS: $FAST_MODEL"
  if run_aider "$FAST_MODEL" 420 diff "$task"; then
    after="$(count_tests)"
    if accept "$task" "$before" "$after" && verify_all; then
      touch "${task}.done"
      rm -f "${task}.blocked"
      rm -f "automation/status/$(basename "$task" .md).blocked.md"
      git add -A
      git commit -m "agent: verified fast $(basename "$task" .md | tr '_' ' ')"
      git push -u origin automation/agent-loop || true; ok=1
    fi
  fi
  [[ $ok -eq 1 ]] && continue

  decision="$(jev_decision "$task" "Groq 20B fast pass failed strict verification")"

  case "$decision" in
    retry|continue)
      echo "Jev allows bounded escalation to $STRONG_MODEL"
      ;;
    *)
      restore "$base"
      status="automation/status/$(basename "$task" .md).blocked.md"
      {
        echo "# Blocked: $(basename "$task")"
        echo
        echo "Jev decision: $decision"
        echo
        echo "Automation stopped fail-closed before the strong-model pass."
      } >"$status"

      touch "${task}.blocked"
      git add "$status" "${task}.blocked"
      git commit -m "chore: Jev requested human review for $(basename "$task")" || true
      git push -u origin automation/agent-loop || true

      echo "STOPPED: Jev requires human review."
      exit 20
      ;;
  esac

  restore "$base"; prep_files "$(basename "$task")"
  echo "ESCALATION PASS: $STRONG_MODEL"
  if run_aider "$STRONG_MODEL" 720 diff "$task"; then
    after="$(count_tests)"
    if accept "$task" "$before" "$after" && verify_all; then
      touch "${task}.done"
      rm -f "${task}.blocked"
      rm -f "automation/status/$(basename "$task" .md).blocked.md"
      git add -A
      git commit -m "agent: verified focused $(basename "$task" .md | tr '_' ' ')"
      git push -u origin automation/agent-loop || true; ok=1
    fi
  fi
  [[ $ok -eq 1 ]] && continue

  restore "$base"
  status="automation/status/$(basename "$task" .md).blocked.md"
  printf '# Blocked: %s\n\nGroq 20B and Groq 120B attempts both failed strict verification.\n' "$(basename "$task")" > "$status"
  touch "${task}.blocked"; git add "$status" "${task}.blocked"
  git commit -m "chore: fast verifier blocked $(basename "$task")" || true
  git push -u origin automation/agent-loop || true
done

echo "== FAST STRICT QUEUE FINISHED =="
echo "Done:"; find automation/tasks -maxdepth 1 -name '0[1-5]_*.done' -printf '  %f\n' | sort
echo "Blocked:"; find automation/tasks -maxdepth 1 -name '0[1-5]_*.blocked' -printf '  %f\n' | sort
pytest -q
