# Multi-engine policy

Primary execution is local and quota-independent:
- Codex CLI as the agent interface
- Ollama as the local inference provider
- Model selected for available WSL RAM: `qwen2.5-coder:3b`

For each task:
1. local attempt;
2. local retry with test/build feedback;
3. optional Codex cloud escalation if authenticated and quota is available;
4. if still not green, restore the last green commit, record a blocker, and continue.

Cloud quota is therefore not a single point of failure.
