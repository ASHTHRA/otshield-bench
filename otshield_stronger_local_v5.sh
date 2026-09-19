#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/otshield-bench"
git switch automation/agent-loop

MODEL="qwen2.5-coder:7b-instruct-q3_K_S"

echo "== OTShield v5: stronger local worker =="
echo "Model: $MODEL"

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >"$HOME/.ollama-otshield.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

ollama pull "$MODEL"

rm -f automation/tasks/01_ground_truth_protocol.md.blocked
rm -f automation/tasks/02_pcap_transaction_correlation.md.blocked
rm -f automation/tasks/03_simulation_adapter.md.blocked
rm -f automation/tasks/04_results_manifest.md.blocked
rm -f automation/tasks/05_reproducibility_release.md.blocked

rm -f automation/status/01_ground_truth_protocol.blocked.md
rm -f automation/status/02_pcap_transaction_correlation.blocked.md
rm -f automation/status/03_simulation_adapter.blocked.md
rm -f automation/status/04_results_manifest.blocked.md
rm -f automation/status/05_reproducibility_release.blocked.md

git add -A
git commit -m "chore: retry strict queue with stronger local coding model" || true
git push -u origin automation/agent-loop || true

python3 - <<'PY'
from pathlib import Path
p = Path("scripts/agent_loop_strict.sh")
s = p.read_text()
old = 'codex exec --oss --local-provider ollama -m "$LOCAL_MODEL" \\\n    --sandbox workspace-write "$prompt"'
new = 'codex exec --oss --local-provider ollama -m "$LOCAL_MODEL" \\\n    --config model_context_window=8192 \\\n    --config model_auto_compact_token_limit=6144 \\\n    --sandbox workspace-write "$prompt"'
if old in s:
    s = s.replace(old, new)
elif "model_context_window=8192" not in s:
    raise SystemExit("Could not safely patch scripts/agent_loop_strict.sh")
p.write_text(s)
PY

git add scripts/agent_loop_strict.sh
git commit -m "chore: tune local Codex metadata for 7B WSL worker" || true
git push -u origin automation/agent-loop || true

echo
echo "Running strict queue with stronger local model and NO cloud fallback..."
LOCAL_MODEL="$MODEL" \
LOCAL_RETRIES=3 \
USE_CLOUD_FALLBACK=0 \
AUTO_PUSH=1 \
bash scripts/agent_loop_strict.sh
