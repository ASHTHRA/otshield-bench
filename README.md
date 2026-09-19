# OTShield Bench

**v0.3.0-alpha** (`0.3.0a0` on Python): a reproducible, vendor-neutral benchmark
for OT cyber-detection effectiveness and resilience using synthetic or normalized
lab-derived Modbus telemetry.

OTShield generates labeled events or ingests passive offline observations, applies
observation faults, runs a detector, and exports evidence and metrics. It never
connects to a PLC or transmits packets. These simplified scenarios and fixtures are
a development benchmark, not validation of protection for a real industrial process.

## Quick start

Requires Python 3.10 or newer.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
otshield --scenario all --detector rules --output results/rules.json
otshield --scenario all --detector iforest --loss 0.1 --latency-ms 10 --jitter-ms 5 --output results/iforest.json
otshield ingest observations.json --output results/normalized.json
```

Alternatively use `python -m otshield.cli`. Omit `--output` to print JSON.
`--count` sets events per scenario (at least 10); `--seed` defaults to 42.
Reports contain original truth, observations, predictions, metrics, configuration,
and Python/scikit-learn versions. Reuse the same environment and seed to reproduce a run.

## Included scenarios

| Scenario | Synthetic anomaly |
| --- | --- |
| normal | None; read holding registers 0–9 |
| unauthorized_write | Unexpected function code 6 |
| register_scan | Out-of-policy register probe at address 1000 |
| polling_burst | Polling interval falls to 5 ms |
| value_spike | Process value rises to 500 |

Anomalies occupy the middle quarter of each non-normal stream. Scenario JSON
definitions ship inside the package. They describe abstract events, not wire packets.

The rule baseline knows the synthetic operating policy. Isolation Forest trains
on a separate normal stream with seed + 1 and never receives labels as features.
It uses scikit-learn's automatic threshold and may have substantial false positives
or miss anomalies in features that are constant during training. Compare measured
results; perfect rule scores on these fixtures do not imply real-world performance.

Packet loss removes observations, and latency/jitter delay arrival and increase
the latency feature. Labels and source polling intervals remain unchanged.
Metrics distinguish observed recall from end-to-end recall under loss.

## Docker/OpenPLC capture scaffolding (v0.3)

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

python scripts/capture_grfics.py     --host 127.0.0.1 --port 502     --output captures/grfics_capture.json     --duration 10 --poll-interval 0.1

otshield ingest captures/grfics_capture.json     --output captures/normalized.json

docker compose -f docker/docker-compose.grfics.yml down -v
```

Requires Docker, Docker Compose, and the capture dependencies documented by the
project. See the GRFICS integration guide for prerequisites and current blockers.

## Passive GRFICSv3/OpenPLC ingestion

v0.3 also accepts strict `OTB-INGEST-SOURCE/0.1` JSON exported from an authorized
GRFICSv3/OpenPLC laboratory or another offline source. It emits deterministic
`OTB-INGEST/0.1` JSON containing unchanged OTB-TELEMETRY/0.1 records, nullable
context, and explicit provenance. Existing synthetic mode remains fully supported.

GRFICSv3 is an independent optional upstream project and is not vendored here.
This repository currently includes only a sanitized GRFICS-like test fixture; no
live GRFICS experiment has been run or claimed. See the
[GRFICS integration guide](docs/grfics-integration.md).

## Project contracts and development

- [OTB-SCENARIO](specs/OTB-SCENARIO.md)
- [OTB-TELEMETRY](specs/OTB-TELEMETRY.md)
- [OTB-DETECT](specs/OTB-DETECT.md)
- [OTB-EVAL](specs/OTB-EVAL.md)
- [OTB-INGEST](specs/OTB-INGEST.md)
- [Architecture and MVP roadmap](docs/architecture.md)

Run `python -m pytest -q` before every commit. CI runs tests on Linux and Windows
with Python 3.10 and 3.12, builds distributions, and smoke-tests the installed wheel.
Changes should follow [the permanent repository instructions](AGENTS.md), keep the
offline OT detection benchmark scope, and use incremental commits.

Licensed under [Apache-2.0](LICENSE).
