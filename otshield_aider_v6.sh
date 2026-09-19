#!/usr/bin/env bash
set -Eeuo pipefail

cd "$HOME/otshield-bench"
git switch automation/agent-loop
export PATH="$HOME/.local/bin:$PATH"

MODEL="qwen2.5-coder:7b-instruct"
AIDER_MODEL="ollama_chat/$MODEL"

echo "== OTShield v6: Aider local editing engine =="
echo "Model: $AIDER_MODEL"

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >"$HOME/.ollama-otshield.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

ollama pull "$MODEL"

if ! command -v aider >/dev/null 2>&1; then
  echo "Installing Aider..."
  curl -LsSf https://aider.chat/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

command -v aider >/dev/null 2>&1 || {
  echo "ERROR: Aider installation did not place 'aider' on PATH."
  exit 1
}

cat > "$HOME/.aider.model.settings.yml" <<EOF
- name: $AIDER_MODEL
  extra_params:
    num_ctx: 8192
EOF

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

cp scripts/agent_loop_strict.sh scripts/agent_loop_aider.sh

python3 - <<'PY'
from pathlib import Path
p = Path("scripts/agent_loop_aider.sh")
s = p.read_text()

start = s.index("run_local() {")
end = s.index("\n}\n\nrun_cloud()", start) + 2

replacement = '''run_local() {
  local prompt="$1"
  local prompt_file
  prompt_file="$(mktemp /tmp/otshield-aider-prompt.XXXXXX)"
  printf '%s\n' "$prompt" >"$prompt_file"

  echo "LOCAL EDIT ENGINE: Aider -> Ollama/$LOCAL_MODEL"

  set +e
  OLLAMA_API_BASE="http://127.0.0.1:11434" \
  AIDER_CHAT_HISTORY_FILE="/tmp/otshield-aider-chat-history.md" \
  AIDER_INPUT_HISTORY_FILE="/tmp/otshield-aider-input-history" \
  aider \
    --model "ollama_chat/$LOCAL_MODEL" \
    --model-settings-file "$HOME/.aider.model.settings.yml" \
    --edit-format whole \
    --message-file "$prompt_file" \
    --yes-always \
    --no-auto-commits \
    --no-dirty-commits \
    --no-gitignore \
    --no-auto-lint \
    --no-auto-test \
    --no-check-update \
    --no-show-release-notes \
    --no-show-model-warnings \
    --no-stream
  local rc=$?
  set -e

  rm -f "$prompt_file"
  return "$rc"
}'''

s = s[:start] + replacement + s[end:]
p.write_text(s)
PY

chmod +x scripts/agent_loop_aider.sh

cat > automation/AIDER_ENGINE.md <<EOF
# Aider local editing engine

The strict autonomous verifier is unchanged.

Local implementation attempts now use:
- Aider as the code-editing agent
- Ollama as the local inference server
- $MODEL as the local code model
- 8192-token Ollama context
- whole-file edit format
- no Aider auto-commits

A task is accepted only by the existing strict git/test/build gates.
EOF

git add -A
git commit -m "chore: switch strict local worker to Aider editing engine" || true
git push -u origin automation/agent-loop || true

echo
echo "Running Aider strict queue with cloud fallback disabled..."
LOCAL_MODEL="$MODEL" \
LOCAL_RETRIES=2 \
USE_CLOUD_FALLBACK=0 \
AUTO_PUSH=1 \
bash scripts/agent_loop_aider.sh
