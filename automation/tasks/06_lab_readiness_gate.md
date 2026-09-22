# Task 06 — v0.6 Lab Readiness Gate

Implement and review a deterministic, fail-closed readiness check for the
replacement v0.6 OpenPLC study. It must establish host, Docker, Compose,
image, network/NIC, container identity, bounded read-only Modbus FC3, capture
tooling, Python dependency, writable path, disk, and lab-lock readiness before
any scientific evidence or study run is created.

Readiness reports must distinguish `PASS`, `FAIL`, `NOT_CHECKED`, and
`EXTERNAL_ACTION_REQUIRED`. OpenPLC may start only after an explicit readiness
command authorization, for a bounded probe, and cleanup must be limited to the
readiness-owned resource. The 125-condition study, detector results, thresholds,
synthetic-to-lab evidence claims, and preserved failed Study B evidence remain
untouched. Use mocked/offline tests, `python -m pytest`, and no automatic Git
publication or task completion marker.
