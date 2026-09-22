# Task 07 — v0.6.1-alpha Release and Independent Validation Package

## Goal

Prepare OTShield Bench for a follow-up v0.6.1-alpha release and independent
third-party validation.

The technical experiment is already complete.

Do NOT rerun experiments.
Do NOT modify existing evidence.
Do NOT publish a GitHub release.
Do NOT create or modify a Zenodo DOI.
Do NOT push tags.
Do NOT claim external replication has already occurred.

## Verified study

Post-release study:

evidence/v06/20260922T174026Z/

Execution commit:

88e1f056dc2143129ef115f3ce1ad731fd0e9a0e

Immutable study-evidence milestone:

340386e9783f450ccf7b30c84557901d87402c90

Documentation milestone:

5616391aea1d4c25ee08a937dd98d41d321bf713

Study facts:

- status: completed
- 25 trials
- 5 conditions
- 125 completed condition runs
- 250 detector evaluations
- 7,500 planned Modbus/TCP transactions
- zero failed attempts
- zero unattempted runs

Existing archived release:

v0.6.0-alpha
DOI: 10.5281/zenodo.22899466

The existing DOI/archive predates the newer study and must remain historical.
Do not represent the old DOI as already containing the post-release study.

## Required implementation

### 1. Create

research/v0.6.1_release_candidate.md

Document:

- purpose of v0.6.1-alpha
- relationship to v0.6.0-alpha
- post-release study path
- execution commit
- evidence milestone
- study dimensions
- primary results
- limitations
- archival boundary

Use accurate claims only.

Explicitly state:

- isolated OpenPLC laboratory
- Modbus/TCP FC3 experimental validation only
- no production validation
- no external replication yet
- no experimental DNP3 validation
- no experimental EtherNet/IP validation
- no universal detector-superiority claim

### 2. Create

research/INDEPENDENT_REPLICATION.md

Write a standalone protocol a third-party engineer/researcher can follow.

Include:

- Linux/WSL2 prerequisites
- Python setup
- Docker/OpenPLC requirements
- repository checkout
- exact reference commit
- readiness checks
- dry-run/preflight
- authorized lab execution
- expected 125 condition runs
- expected 250 detector evaluations
- output layout
- SHA-256 verification
- comparison with reference aggregate
- reporting failures/deviations

Do not require identical CPU or wall-time measurements.

### 3. Create

research/replication_result_template.md

Include fields for:

- researcher
- organization
- date
- operating system
- CPU
- RAM
- Docker version
- Python version
- OTShield commit
- completed runs
- failed runs
- baseline recall/F1 by condition
- robust recall/F1 by condition
- paired differences
- integrity verification
- protocol deviations
- observations
- environment-limited conclusion

### 4. Create

research/VALIDATION_REQUEST.md

Create a concise professional outreach message for:

- OT cybersecurity researchers
- ICS security labs
- university researchers
- automation/control researchers
- industrial security practitioners

Ask for:

- independent reproduction
- technical review
- GitHub issue reports
- methodological feedback
- citation only if genuinely relevant to their work

Do not exaggerate project maturity.

### 5. Create

scripts/verify_v061_release.py

It must be read-only and non-destructive.

Verify:

- evidence/v06/20260922T174026Z exists
- study.json exists
- status == completed
- execution_git_commit ==
  88e1f056dc2143129ef115f3ce1ad731fd0e9a0e
- completed_condition_runs == 125
- completed_detector_evaluations == 250
- failed_attempts is empty
- unattempted_runs is empty
- aggregate.json exists
- calibration.json exists
- execution.json exists
- experiment_protocol.md exists
- STUDY_SHA256SUMS exists
- required research documents reference the correct post-release study
- old v0.6.0-alpha DOI is not described as containing the new study

Return nonzero on failure.

Never modify evidence.

### 6. Add

tests/test_verify_v061_release.py

Test at least:

- valid completed study
- incorrect execution commit
- incomplete status
- failed attempt present
- missing aggregate.json
- incorrect old-DOI/new-study archival claim

### 7. Verification

Run:

python -m pytest -q

python -m build

python scripts/verify_v061_release.py

Fix legitimate failures.

Do not alter scientific evidence just to satisfy tests.

## Required final response

Report:

1. files created or changed
2. pytest result
3. build result
4. release verifier result
5. blockers
6. recommended human publication step

## Success condition

A new OT/ICS researcher should be able to understand how to independently
validate the completed OTShield study without contacting the original author.
