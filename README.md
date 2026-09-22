# OTShield Bench

**v0.6.0-alpha** (`0.6.0a0` on Python) is the current research release candidate:
a reproducible, vendor-neutral benchmark for OT cyber-detection effectiveness,
resource cost, and resilience using synthetic
and isolated lab-derived Modbus telemetry.

OTShield generates labeled events or ingests passive offline observations, applies
observation faults, runs detectors, and exports evidence and metrics. Its core
benchmark path is offline. Separately, the repository includes isolated laboratory
runners that generate bounded read-only Modbus/TCP Function Code 3 traffic against
the documented OpenPLC test environment. These scenarios and laboratory measurements
are research evidence, not validation of protection for a production industrial process.

The completed v0.6 paired study contains **125 condition runs** (25 trials × five
conditions), 7,500 planned transactions, and 250 baseline/robust detector evaluations.
The robust threshold was frozen from independent historical clean calibration.
Within the documented isolated OpenPLC lab and preregistered timing setup, it
showed materially greater resilience under the heavier tested delay conditions,
with no observed recall/F1 penalty under clean and lighter tested conditions.
Coverage was 1.0 and false positives were zero across all conditions.

See the [v0.6 findings](research/v0.6_findings.md),
[v0.6 technical report](research/OTShield_Bench_v0.6_Technical_Report.md),
[release notes](research/v0.6_release_notes.md), and
[release manifest](research/v0.6_release_manifest.md).

## Citation

The **current archived release, OTShield Bench v0.6.0-alpha**, is published on
[GitHub](https://github.com/ASHTHRA/otshield-bench/releases/tag/v0.6.0-alpha)
and archived on Zenodo:

**DOI:** [10.5281/zenodo.22899466](https://doi.org/10.5281/zenodo.22899466)

The **previous archived release, OTShield Bench v0.5.1-alpha**, is permanently
available through Zenodo:

**DOI:** [10.5281/zenodo.22863660](https://doi.org/10.5281/zenodo.22863660)

Current release citation metadata is provided in [`CITATION.cff`](CITATION.cff).

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

## OpenPLC laboratory evidence

OTShield now includes measured evidence from an isolated Docker-based OpenPLC
laboratory using read-only Modbus/TCP Function Code 3 traffic.

The repository contains:

- raw PCAP captures with SHA-256 integrity hashes;
- explicit laboratory provenance;
- transaction-aware Modbus/TCP normalization;
- a measured normal polling baseline;
- a predeclared labeled polling-burst experiment;
- degraded-connectivity experiments using controlled delay, jitter, and loss;
- the historical v0.5 five-trial repeatability study covering 25 condition runs
  and 1,500 planned read-only Modbus/TCP transactions;
- the completed v0.6 125-run paired study, with frozen calibration, readiness
  checks, infrastructure hardening, and separately preserved failed attempts.

The current evidence comes from a minimal isolated OpenPLC environment using the
configured GRFICS-derived PLC image. It must **not** be represented as a completed
full GRFICSv3 process simulation, production OT validation, independent external
replication, or general cybersecurity effectiveness validation.

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
The repository includes both sanitized fixtures and separately identified
laboratory-derived OpenPLC evidence. A full GRFICSv3 process simulation has not
yet been completed or claimed. See the
[GRFICS integration guide](docs/grfics-integration.md).

## Reproducibility and release verification

Run the complete local verification with:

`./scripts/verify_release.sh`

The command runs repository checks, the complete test suite, and the Python
package build. See [docs/reproducibility.md](docs/reproducibility.md) for the
research-release checklist and evidence boundaries.

Capabilities retained from v0.5 include passive offline Modbus/TCP PCAP transaction
correlation, explicit lab provenance, measured resource-cost reporting,
predeclared timing ground truth, degraded-connectivity evaluation, repeatability
statistics, and versioned benchmark result manifests.

A completed full GRFICSv3 process simulation and independent external replication
remain future milestones.
Repository scaffolding and sanitized fixtures are not evidence of completed
laboratory or real-world validation.

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
