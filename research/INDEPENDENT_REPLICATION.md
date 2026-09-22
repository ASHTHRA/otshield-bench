# Independent Replication Guide

This document provides step-by-step instructions for a Linux/WSL2 researcher
to independently replicate the OTShield Bench v0.6.1 study.

## Prerequisites

### Hardware

- A Linux or WSL2 machine with sufficient resources to run OpenPLC and
  OTShield Bench (refer to the project's resource requirements for minimum
  specifications).

### Software

- **Python** 3.11 or later (verify with `python3 --version`).
- **Docker** and **Docker Compose** installed and running (verify with
  `docker --version` and `docker compose version`).
- **Git** installed (verify with `git --version`).
- **OpenPLC** runtime available via the project's configured Docker image.

## Checkout

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd otshield-bench
   ```

2. Check out the study execution commit:

   ```bash
   git checkout 88e1f056dc2143129ef115f3ce1ad731fd0e9a0e
   ```

3. Verify the checkout matches the expected commit hash.

## Python Environment Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Verify the installation:

   ```bash
   python3 -c "import otshield; print(otshield.__version__)"
   ```

## Docker / OpenPLC Setup

1. Ensure Docker is running:

   ```bash
   docker info
   ```

2. Start the OpenPLC laboratory container using the project's compose
   configuration:

   ```bash
   docker compose up -d
   ```

3. Verify the OpenPLC service is healthy before proceeding.

## Readiness Check

Run the readiness check to confirm all prerequisites are satisfied:

```bash
python3 -m otshield.preflight --compose-file <path-to-compose> --runtime <path-to-runtime>
```

All checks should pass before attempting the study execution.

## Dry Run

Perform a dry run to validate the execution plan without running trials:

```bash
python3 -m otshield.run --dry-run --trials 25 --conditions 5
```

Confirm the plan reports **125 planned condition runs** and **250 detector
evaluations** before proceeding to authorized execution.

## Authorized Execution

1. Obtain the required authorization to execute the study.

2. Run the study with authorization enabled:

   ```bash
   python3 -m otshield.run --authorized --trials 25 --conditions 5
   ```

3. Expected outcomes:
   - **125 completed condition runs**
   - **250 detector evaluations**
   - **7,500 planned transactions**
   - **0 failed attempts**
   - **0 unattempted runs**

## Output Structure

Results are written to a new evidence directory under
`evidence/v06/<NEW_UTC_TIMESTAMP>/`, where `<NEW_UTC_TIMESTAMP>` is the UTC
timestamp printed by `scripts/run_v06_study.py` when the run finishes.
The reference study directory `evidence/v06/20260922T174026Z/` is reference
evidence only and must not be used as an output directory.

The independent study should contain study-level records including:

- `study.json`
- `aggregate.json`
- `calibration.json`
- `execution.json`
- `execution.log`
- `experiment_protocol.md`
- `STUDY_SHA256SUMS`

and may contain run-level evidence retained by the study pipeline.

## SHA-256 Verification

After execution, enter the NEW study directory created for your independent run:

    cd evidence/v06/<NEW_UTC_TIMESTAMP>/
    sha256sum -c STUDY_SHA256SUMS

A successful verification means the retained artifacts agree with that independent study own integrity inventory.

Do not expect your SHA-256 hashes to match the reference study. Timestamps, execution logs, runtime measurements, metadata, and reproduced observations may differ.

The reference study remains:

`evidence/v06/20260922T174026Z/`

and must not be modified during replication.

## Result Comparison

Compare your reproduced study against:

- `evidence/v06/20260922T174026Z/study.json`
- `evidence/v06/20260922T174026Z/aggregate.json`

Compare at minimum:

- study status
- completed condition runs
- completed detector evaluations
- failed and unattempted runs
- baseline recall and F1 by condition
- robust recall and F1 by condition
- paired robust-minus-baseline effects

Do not require identical CPU time, wall time, traced-memory measurements, timestamps, raw hashes, or byte-identical artifacts.

## Deviation Reporting

If your results deviate from the reference results:

1. Document the deviation in your result files.
2. Report the deviation magnitude for each metric (recall, F1).
3. Note any environmental differences that may explain the deviation.
4. File an issue in the repository with your findings.

## Scope Limitations

This replication covers Modbus/TCP FC3 experimental validation only, in an
isolated OpenPLC laboratory. No production validation, external replication,
DNP3, or EtherNet/IP validation is included. No universal detector-superiority
claim is made.
