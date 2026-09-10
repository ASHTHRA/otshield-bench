# OTShield Bench

**v0.1.0-alpha** (`0.1.0a0` on Python): a reproducible, offline benchmark for
operational technology anomaly detection using synthetic Modbus-like telemetry.

OTShield generates labeled events, applies observation faults, runs a detector,
and exports evidence and metrics. It never connects to a PLC or transmits packets.
These simplified scenarios are a development benchmark, not validation of protection
for a real industrial process.

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

## Project contracts and development

- [OTB-SCENARIO](specs/OTB-SCENARIO.md)
- [OTB-TELEMETRY](specs/OTB-TELEMETRY.md)
- [OTB-DETECT](specs/OTB-DETECT.md)
- [OTB-EVAL](specs/OTB-EVAL.md)
- [Architecture and MVP roadmap](docs/architecture.md)

Run `python -m pytest -q` before every commit. CI runs tests on Linux and Windows
with Python 3.10 and 3.12, builds distributions, and smoke-tests the installed wheel.
Changes should keep the offline OT detection benchmark scope and use incremental commits.

Licensed under [Apache-2.0](LICENSE).
