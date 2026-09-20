# Reproducing OTShield Bench v0.5.0-alpha

This guide reproduces the software verification and identifies the isolated-lab entry point for the v0.5 evidence.

## 1. Verify the immutable release

```bash
git clone https://github.com/ASHTHRA/otshield-bench.git
cd otshield-bench
git checkout v0.5.0-alpha
git rev-parse HEAD
```

Expected release commit:

```text
8f79f77f6a410d4c648ca7dbddd3e1b5a4148edb
```

## 2. Create a Python environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell use `.venv\Scripts\Activate.ps1`.

## 3. Run the release verification gate

```bash
./scripts/verify_release.sh
```

The release gate checks repository state, runs the complete pytest suite, and builds source and wheel distributions.

## 4. Inspect the published repeatability evidence

The v0.5 repeatability study is stored under:

```text
evidence/repeatability/20260920T182506Z/
```

Key files:

- `study.json` - study manifest and run count
- `aggregate.json` - run-level statistics, including bounded display and unbounded Student-t intervals
- `aggregate.md` - human-readable summary
- `trial-*/<condition>/raw.pcap` - captured packets
- `trial-*/<condition>/protocol.json` - predeclared ground truth and condition
- `trial-*/<condition>/provenance.json` - environment and evidence provenance
- `trial-*/<condition>/normalized.json` - transaction-aware normalized telemetry
- `trial-*/<condition>/observations.json` - observed detector inputs/outputs
- `trial-*/<condition>/result.json` - benchmark result manifest
- `trial-*/<condition>/SHA256SUMS` - per-run integrity hashes

## 5. Re-run the isolated lab study

Only use the runner in an authorized isolated laboratory. The runner generates bounded read-only Modbus/TCP Function Code 3 traffic against the project OpenPLC test environment.

Prerequisites include a functioning Docker Engine and Docker Compose.

```bash
TRIALS=5 ./scripts/run_resilience_replicates.sh
```

The runner executes five conditions, rotates their order between trials, captures traffic in the OpenPLC/server network namespace, normalizes each PCAP, evaluates the fixed polling-burst detector, records provenance and hashes, and emits aggregate repeatability statistics.

## 6. Evidence boundary

Reproduction of this release verifies the documented software and isolated OpenPLC laboratory method. It does not establish production OT performance, full GRFICSv3 process-simulation validation, DNP3/EtherNet-IP validation, or general cybersecurity effectiveness.
