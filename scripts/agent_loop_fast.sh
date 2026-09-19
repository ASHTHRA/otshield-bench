#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"
FAST_MODEL="${FAST_MODEL:-qwen2.5-coder:3b}"
STRONG_MODEL="${STRONG_MODEL:-qwen2.5-coder:7b-instruct}"

count_tests(){ pytest --collect-only -q 2>/dev/null | tail -n1 | grep -oE '[0-9]+ test' | grep -oE '[0-9]+' || echo 0; }
verify_all(){ pytest -q && python -m build; }
restore(){ git reset --hard "$1" >/dev/null; git clean -fd -e .venv/ -e captures/ -e dist/ -e 'otshield_*.sh' -e automation/status/ >/dev/null; }

prep_files(){
  case "$1" in
    01_ground_truth_protocol.md)
      touch src/otshield/ground_truth.py tests/test_ground_truth.py docs/ground-truth.md
      FILES=(src/otshield/ground_truth.py src/otshield/core.py src/otshield/evaluation.py src/otshield/cli.py tests/test_ground_truth.py tests/test_bench.py docs/ground-truth.md);;
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
  timeout --signal=INT --kill-after=30s "${timeout_s}s" env OLLAMA_API_BASE=http://127.0.0.1:11434 aider \
    --model "ollama_chat/$model" \
    --model-settings-file "$HOME/.aider.otshield-fast.yml" \
    --edit-format "$fmt" --map-tokens 512 --map-refresh files --max-chat-history-tokens 1024 \
    --message-file "$pf" --yes-always --no-auto-commits --no-dirty-commits \
    --no-auto-lint --no-auto-test --no-check-update --no-show-release-notes --no-stream \
    "${args[@]}"
  rc=$?; set -e; rm -f "$pf"; return $rc
}

accept(){
  local task="$1" before="$2" after="$3" files
  files="$(git status --porcelain | awk '{print $2}' | grep -vE '^automation/(tasks|status)/' || true)"
  [[ -n "$files" ]] || return 1
  case "$(basename "$task")" in
    01_*|02_*|03_*|04_*)
      echo "$files" | grep -q '^src/otshield/' || return 1
      echo "$files" | grep -q '^tests/' || return 1
      (( after > before )) || return 1;;
    05_*) echo "$files" | grep -Eq '^(scripts/|docs/|README\.md)' || return 1;;
  esac
}

for task in automation/tasks/0{1,2,3,4,5}_*.md; do
  [[ -e "$task" ]] || continue
  [[ -e "${task}.done" ]] && continue
  base="$(git rev-parse HEAD)"; before="$(count_tests)"; ok=0
  echo "===== FAST TASK: $(basename "$task") ====="

  restore "$base"; prep_files "$(basename "$task")"
  echo "FAST PASS: $FAST_MODEL"
  if run_aider "$FAST_MODEL" 420 diff "$task"; then
    after="$(count_tests)"
    if accept "$task" "$before" "$after" && verify_all; then
      touch "${task}.done"; rm -f "${task}.blocked"; git add -A
      git commit -m "agent: verified fast $(basename "$task" .md | tr '_' ' ')"
      git push -u origin automation/agent-loop || true; ok=1
    fi
  fi
  [[ $ok -eq 1 ]] && continue

  restore "$base"; prep_files "$(basename "$task")"
  echo "ESCALATION PASS: $STRONG_MODEL"
  if run_aider "$STRONG_MODEL" 720 whole "$task"; then
    after="$(count_tests)"
    if accept "$task" "$before" "$after" && verify_all; then
      touch "${task}.done"; rm -f "${task}.blocked"; git add -A
      git commit -m "agent: verified focused $(basename "$task" .md | tr '_' ' ')"
      git push -u origin automation/agent-loop || true; ok=1
    fi
  fi
  [[ $ok -eq 1 ]] && continue

  restore "$base"
  status="automation/status/$(basename "$task" .md).blocked.md"
  printf '# Blocked: %s\n\nFast 3B and focused 7B attempts both failed strict verification.\n' "$(basename "$task")" > "$status"
  touch "${task}.blocked"; git add "$status" "${task}.blocked"
  git commit -m "chore: fast verifier blocked $(basename "$task")" || true
  git push -u origin automation/agent-loop || true
done

echo "== FAST STRICT QUEUE FINISHED =="
echo "Done:"; find automation/tasks -maxdepth 1 -name '0[1-5]_*.done' -printf '  %f\n' | sort
echo "Blocked:"; find automation/tasks -maxdepth 1 -name '0[1-5]_*.blocked' -printf '  %f\n' | sort
pytest -q
