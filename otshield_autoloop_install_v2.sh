#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${HOME}/otshield-bench"
BRANCH="automation/agent-loop"

if [[ ! -d "$REPO/.git" ]]; then
  echo "ERROR: expected git repo at $REPO"
  exit 1
fi

cd "$REPO"
echo "== OTShield Bench guarded autonomous setup v2 =="

# Keep autonomous work isolated from main while preserving local v0.3 changes.
if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git switch "$BRANCH"
  else
    git switch -c "$BRANCH"
  fi
fi

# Correct known v0.3 README overclaims/path issue before checkpointing.
python3 - <<'PY'
from pathlib import Path
p = Path("README.md")
if not p.exists():
    raise SystemExit("README.md not found")

s = p.read_text()

start = "## Docker-based GRFICSv3/OpenPLC integration (v0.3)"
end = "## Passive GRFICSv3/OpenPLC ingestion"

if start in s and end in s:
    a, rest = s.split(start, 1)
    _, b = rest.split(end, 1)
    safe = """## Docker/OpenPLC capture scaffolding (v0.3)

v0.3 adds Docker/OpenPLC integration scaffolding for generating and normalizing
Modbus TCP telemetry when a compatible laboratory environment is available.
The repository includes capture/orchestration code, validation checks, and
provenance-aware normalization, but a full GRFICSv3 lab run has **not yet been
validated in this project environment**.

The current workstation still requires the documented Docker/Compose/network
prerequisites before real GRFICS/OpenPLC captures can be claimed as benchmark
evidence. Any synthetic fixtures remain explicitly labeled synthetic.

```sh
# From the repository root, after Docker prerequisites are available:
docker compose -f docker/docker-compose.grfics.yml up -d openplc

python scripts/capture_grfics.py \
    --host 127.0.0.1 --port 502 \
    --output captures/grfics_capture.json \
    --duration 10 --poll-interval 0.1

otshield ingest captures/grfics_capture.json \
    --output captures/normalized.json

docker compose -f docker/docker-compose.grfics.yml down -v
```

Requires Docker, Docker Compose, and the capture dependencies documented by the
project. See the GRFICS integration guide for prerequisites and current blockers.

"""
    s = a + safe + end + b
    p.write_text(s)
    print("README: corrected v0.3 validation wording and root-relative paths.")
else:
    print("README: known block not found; leaving content unchanged for agent claim audit.")
PY

# Python environment
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e '.[dev]'

echo "Running preflight tests/build..."
pytest -q
python -m build >/dev/null

# Checkpoint local v0.3 safely.
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  if git diff --cached --name-only | grep -E '(^|/)(\.env|captures/|\.venv/|dist/|build/)' >/dev/null; then
    echo "ERROR: generated/private files would be committed. Nothing committed."
    git reset
    exit 2
  fi
  git commit -m "checkpoint: v0.3 implementation, runtime validation pending"
fi

mkdir -p automation/tasks scripts

cat > automation/AGENT_GUARDRAILS.md <<'EOF'
# OTShield Bench autonomous-agent guardrails

You are developing an open, reproducible OT/ICS cybersecurity benchmark.

Non-negotiable rules:
1. Never fabricate measurements, packet captures, detector results, GRFICS execution, Docker execution, hardware availability, CI outcomes, publications, users, or adoption.
2. Synthetic fixtures must be explicitly identified as synthetic. Lab-derived data must include provenance.
3. Do not claim GRFICSv3/OpenPLC runtime validation unless the environment actually ran it and produced verifiable artifacts.
4. Do not call code "deterministic" when wall-clock timing, Docker scheduling, packet timing, or network behavior can vary; distinguish deterministic data generation from runtime timing.
5. Do not weaken/delete tests merely to get a green run.
6. Never commit secrets, credentials, tokens, .env files, raw sensitive captures, build artifacts, or virtual environments.
7. The outer harness owns commits, pushes, tags, merges, and releases.
8. Preserve backward compatibility unless a task explicitly requires a versioned breaking change.
9. Favor deterministic offline tests and small dependencies.
10. Every implemented capability needs tests and concise documentation.
11. When blocked by Docker, NIC/macvlan, RAM, hardware, or external services, implement only safe offline scaffolding/tests and document the blocker truthfully.
12. Keep tooling defensive/benchmark-oriented: no exploit automation, credential theft, persistence, evasion, destructive control logic, or active attack execution.
13. Record seed/version/config/provenance where applicable.
14. Audit documentation against actual repository evidence before making research claims.
EOF

cat > automation/tasks/00_claim_audit.md <<'EOF'
Audit all v0.3 documentation and code comments for claims that exceed repository evidence.

Specifically:
- distinguish implemented code from runtime-validated experiments;
- ensure no text says a GRFICS/OpenPLC lab, real capture, Docker experiment, or benchmark measurement succeeded unless an artifact proves it;
- avoid describing network packet timing as fully deterministic merely because polling/configuration is seeded;
- verify README command paths against the actual repository layout;
- keep current blockers explicit;
- add/update tests only if needed to prevent misleading examples.
Make the smallest truthful documentation fixes required.
EOF

cat > automation/tasks/01_ground_truth_protocol.md <<'EOF'
Implement deterministic ground-truth derivation from an explicit experiment protocol.

Goal:
- Define a small versioned protocol schema for experiment phases/events.
- Derive expected labels/windows from that protocol without inventing observations.
- Keep synthetic and lab-derived provenance distinct.
- Add tests for valid protocols, malformed input, overlapping windows, and deterministic output.
- Document schema and CLI/API usage.
- Do not require live GRFICS or Docker.
EOF

cat > automation/tasks/02_pcap_transaction_correlation.md <<'EOF'
Add an offline, defensive Modbus/TCP PCAP ingestion path with request/response transaction correlation.

Constraints:
- Local capture files only.
- Correlate using defensible fields such as connection tuple and Modbus transaction identifier.
- Handle retransmission, duplicates, and unmatched requests/responses explicitly.
- Preserve timestamps and provenance.
- Use small generated/sanitized test fixtures only.
- If packet decoding needs an optional dependency, document it.
- No active scanning, exploitation, packet injection, or control commands.
EOF

cat > automation/tasks/03_simulation_adapter.md <<'EOF'
Harden the simulation-container adapter without pretending a full GRFICSv3 lab exists.

Goal:
- Provide a deterministic interface/config for launching or attaching to a simulation when Docker is available.
- Add preflight checks for Docker/Compose/network prerequisites.
- Fail closed with clear diagnostics when macvlan/NIC/RAM prerequisites are absent.
- Add unit tests using mocks only.
- Keep real lab execution as an explicit external milestone.
EOF

cat > automation/tasks/04_results_manifest.md <<'EOF'
Create a versioned benchmark result manifest and report generator.

Goal:
- Capture benchmark version, detector adapter, protocol, seed, provenance, environment metadata, effectiveness metrics, measured resource-cost metrics, and degraded-connectivity settings.
- Generate a concise Markdown summary.
- Validate missing/invalid fields.
- Add deterministic tests and synthetic examples clearly labeled synthetic.
- Never populate unmeasured values with invented numbers.
EOF

cat > automation/tasks/05_reproducibility_release.md <<'EOF'
Improve reproducibility and research-release readiness.

Goal:
- Add a single local verification command/script for tests plus package build.
- Update documentation explaining implemented vs planned capabilities.
- Keep v0.3 blockers explicit.
- Add a reproducibility checklist for an eventual public technical report/dataset release.
- Do not claim publication, peer review, real-world validation, or completed GRFICS experiments unless evidence exists.
EOF

cat > scripts/agent_loop.sh <<'EOF'
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
EOF

chmod +x scripts/agent_loop.sh

cat > automation/README.md <<'EOF'
# OTShield autonomous development loop

This loop processes the task queue using Codex in workspace-write sandbox mode.

Safety:
- never runs automated work on main;
- tests and builds current v0.3 before agent work;
- first task audits research/documentation claims;
- verifies full tests/build after every task;
- rolls back failed iterations;
- commits/pushes only the automation branch;
- never automatically merges to main.
EOF

git add automation scripts/agent_loop.sh README.md
git commit -m "chore: add guarded autonomous development loop" || true

git push -u origin "$BRANCH" || {
  echo "WARNING: GitHub push failed. Local loop can still run."
}

echo
echo "Starting autonomous development..."
bash scripts/agent_loop.sh
