# Architecture and v0.1 MVP roadmap

OTShield Bench measures OT anomaly detectors on controlled synthetic observations.
Its trust boundary is local Python data: no live industrial system is involved.

```text
Bundled scenario JSON -> seeded generator -> immutable truth -----------------+
                                             |                              |
                                       loss/delay faults                    |
                                             |                              |
                                         observations -> detector -> identity join
                                                            |               |
Separate normal training stream -> Isolation Forest          +-----> metrics + JSON
```

`core.py` owns event validation, generation, and fault simulation. `detectors.py`
owns the feature boundary and detector results. `evaluation.py` aligns identities
and calculates metrics. `cli.py` orchestrates runs and records evidence. Resource
files are packaged so installed wheels work outside the repository.

Local random generators avoid global RNG mutation. Different seeds separate
training (+1), evaluation (+0), and observation faults (+2). Ground truth is
retained before faults. Model scores use no truth labels. Synthetic anomalies
do not modify the subsequent process state; this is not a digital twin.

## Alpha acceptance

- Five deterministic, safe scenarios and documented versioned contracts.
- Rule and Isolation Forest baselines with explicit training and scoring behavior.
- Packet loss, fixed latency, jitter, arrival reordering, and coverage-aware metrics.
- CLI JSON export, pytest regression suite, installable wheel, and CI.

## Remaining work toward stable v0.1

1. Add machine-readable JSON Schemas and validated external scenario loading.
2. Add repeated-seed experiment suites, aggregate metrics, and confidence intervals.
3. Calibrate anomaly thresholds on a separate validation stream and record provenance.
4. Add episode detection delay and scenario parameter sweeps without label leakage.
5. Expand abstract Modbus transaction semantics and process-state consistency.

Keep these extensions offline by default. Live adapters, packet capture ingestion,
and deployment claims require a separately specified scope and are not alpha features.
