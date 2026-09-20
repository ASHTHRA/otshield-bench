# OTShield Bench Reproducibility

## Verification

Run the complete local verification from the repository root:

`./scripts/verify_release.sh`

The command checks repository whitespace/errors, runs the complete test suite,
and builds both Python source and wheel distributions.

## Implemented v0.3 capabilities

The current development line includes:

- deterministic synthetic OT telemetry scenarios;
- rule and Isolation Forest detector baselines;
- effectiveness and degraded-connectivity evaluation;
- versioned telemetry and ingestion schemas;
- explicit provenance;
- ground-truth protocol support;
- passive structured-data ingestion;
- passive classic-PCAP Ethernet/IPv4/TCP/Modbus-TCP parsing;
- Modbus request/response correlation;
- duplicate/retransmission accounting;
- unmatched-request and unmatched-response reporting;
- deterministic sanitized PCAP fixtures;
- fail-closed Docker/simulation prerequisite checks;
- deterministic simulation command construction;
- versioned `OTB-RESULT/0.1` result manifests;
- deterministic JSON and Markdown benchmark reporting;
- explicit representation of unmeasured resource-cost fields.

## Current evidence boundary

The repository does not currently claim:

- a completed full GRFICSv3 laboratory deployment;
- completed OpenPLC/GRFICS experimental validation;
- production OT deployment;
- real-world cybersecurity effectiveness validation;
- peer review;
- publication;
- independent replication;
- industry adoption.

Configuration files, mocked tests, simulation preflight code, and sanitized
fixtures are not evidence that a real laboratory experiment occurred.

## Reproducibility checklist

Before a technical report, dataset, or benchmark release, record:

### Source

- repository URL;
- exact commit SHA;
- benchmark/release version;
- schema versions.

### Environment

- operating system;
- Python version;
- dependency versions;
- CPU and RAM where measurements depend on them;
- Docker and Docker Compose versions for container experiments;
- relevant network topology and interfaces.

### Benchmark configuration

- detector adapter and version;
- protocol;
- scenario;
- seed;
- loss setting;
- latency setting;
- jitter setting.

### Dataset provenance

- source classification;
- dataset identifier;
- evidence type;
- acquisition/export procedure;
- time basis;
- integrity hash;
- ground-truth procedure.

Synthetic data must remain labeled synthetic.

Sanitized fixtures must not be represented as laboratory captures.

### Measurements

Record effectiveness metrics together with observation coverage and degradation
settings.

Resource-cost values must be based on actual measurements. An unavailable
measurement must remain null or explicitly unmeasured rather than being replaced
with an estimated or invented value.

### Verification

Before a release candidate:

- run `./scripts/verify_release.sh`;
- confirm the complete test suite passes;
- confirm source and wheel distributions build;
- reproduce deterministic outputs from a clean checkout;
- verify documentation claims match the available evidence.

## Future GRFICS/OpenPLC milestone

A future external laboratory milestone can include:

1. provision an isolated authorized host;
2. install and record Docker/Compose versions;
3. document the host NIC and network topology;
4. verify RAM/storage prerequisites;
5. pin upstream GRFICS/OpenPLC revisions;
6. pass OTShield simulation preflight;
7. launch the isolated laboratory;
8. passively capture traffic;
9. preserve hashes, timestamps, configuration and provenance;
10. generate benchmark result manifests from measured data.

Until those activities are actually executed and documented, they remain planned
work rather than completed experimental evidence.

## Research-release artifacts

A future reproducible release should contain:

- source commit or tag;
- environment information;
- experiment protocol;
- ground-truth protocol;
- dataset provenance;
- integrity hashes;
- benchmark result manifests;
- reproduction commands;
- limitations and threats-to-validity documentation.

This separation between implemented software, measured evidence, and external
validation is a core OTShield Bench reproducibility principle.
