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

## Current Groq/Aider runner

`scripts/agent_loop_fast.sh` now delegates to `python -m scripts.agent_runner`.
The older loop scripts are legacy entrypoints; the behavior described above is
not the contract for the new fast runner. Do not use legacy loops for this workflow.

The fast runner skips `.done` and `.blocked` tasks unconditionally. `ONLY_TASK`
(or `--only-task`) narrows selection; `FORCE_TASK` no longer bypasses completion.
It requires a clean checkout and a passing baseline (`python -m pytest -q` and
`python -m build`), then clones HEAD into an ignored, private
`.otshield-runtime/candidate-*` directory. The source checkout is never reset or
cleaned. Repository and `src` imports use absolute candidate paths and the current
Python interpreter. A reset/clean import regression test uses a disposable repo.

Aider uses Groq's fast model, with at most one strong-model repair if the
fail-closed Jev/TypeSafe gate returns `retry` or `continue`. Jev cannot bypass
verification or declare a task complete. Failed edits stay in the candidate for
review. A successful test/build is a candidate for human review, not scientific
validation or automatic completion. The runner processes one pending task per
invocation and never commits, pushes, merges, tags, releases, or writes task markers.
Review the candidate diff and evidence before integrating it and marking completion.
Candidates are development isolation, not a security sandbox for untrusted code.

### v0.6 lab readiness

Before any replacement v0.6 study is authorized, run:

```sh
python -m scripts.v06_lab_readiness
```

This performs a deterministic host gate and writes JSON plus Markdown reports
under `.otshield-runtime/v06-readiness/`. It never creates `evidence/v06`, runs
the 125-condition study, changes detector thresholds, or treats synthetic tests
as laboratory evidence. Docker/OpenPLC startup and one bounded read-only FC3
probe require the explicit opt-in:

```sh
python -m scripts.v06_lab_readiness --authorize-start
```

The opt-in uses a unique Compose project, resolves the host port from the
Compose mapping, captures the full container identity, then waits up to 60
seconds with bounded retries. Each attempt checks the identity, opens the TCP
endpoint first, and only then performs one read-only FC3 request. It removes
only the container and Compose network owned by that readiness invocation; it
also removes earlier empty networks carrying the readiness project label.
Reports use `PASS`, `FAIL`,
`NOT_CHECKED`, and `EXTERNAL_ACTION_REQUIRED`; missing images and macvlan/NIC
requirements identify the exact external action. A readiness pass is a host
prerequisite result, not scientific evidence and not permission to start the
study without separate human approval.

### Optional Soup context

The audit found `soup-ai==0.2.1` in `.soup-venv`, but no tracked Soup integration in
the starting checkout. `scripts/soup_context.py` now registers three small local
contexts and uses Soup's offline router. No remote skills, provider calls or keys
are needed. Set `SOUP_PYTHON` to an interpreter with `soup-ai==0.2.1`; the runner
also discovers `.soup-venv/bin/python`. Without Soup, or on routing failure, the
runner uses the original task and permanent instructions. Soup is optional and
is not a benchmark runtime dependency.

`AGENTS.md`, `automation/AGENT_GUARDRAILS.md`, and the runner's fixed workflow rules
are always included outside Soup routing. Soup cannot select away safety or
evidence policy. Aider receives the Groq key only; Jev receives the TypeSafe key
only. Routing and verification receive neither. Raw provider output is not logged
or forwarded to Jev, Aider histories are disabled, and Jev exceptions are redacted.
Supply credentials through the calling environment, never task files or Git.

Offline smoke (does not execute or reopen any queued task):

```sh
python -m scripts.agent_runner --smoke
python -m pytest -q tests/test_agent_runner.py
```

Tests cover permanent policy, fallback, credential scoping, completed/blocked
selection, bounded escalation, fail-closed decisions and imports after reset/clean.
The installed-Soup integration test skips if its optional environment is absent;
the explicit smoke command fails when Soup is unavailable. These checks provide
software integration evidence only, not live Groq/Jev or laboratory validation.

Task 03's artificial blocked marker/report were removed: completion originates
in `8a7cba9`, while `066c861` added only the contradictory forced-rerun block.
Its `.done` marker and implementation remain intact.
