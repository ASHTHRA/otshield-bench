# GRFICS/OpenPLC Integration Status

## Current scope

OTShield Bench treats GRFICS/OpenPLC as an optional external laboratory source.

The repository does **not** claim that a full GRFICS laboratory has been
successfully deployed or executed as part of the current milestone.

Implemented capabilities include:

- offline structured telemetry ingestion;
- provenance-preserving normalization;
- passive classic-PCAP Modbus/TCP parsing;
- request/response transaction correlation;
- duplicate/retransmission accounting;
- unmatched transaction reporting;
- deterministic simulation prerequisite checks.

## Simulation adapter

`SimulationContainerAdapter` provides a fail-closed interface for an eventual
authorized Docker-based simulation environment.

Its `preflight()` method checks:

- Docker CLI availability;
- Docker Compose availability;
- compose configuration presence;
- minimum host RAM;
- required parent network interface;
- macvlan configuration when required.

A failed prerequisite produces explicit diagnostics. OTShield does not silently
assume that a host can run the laboratory.

The adapter can deterministically construct commands for:

- `launch`
- `attach`
- `status`
- `stop`

Command construction itself performs no Docker action.

Explicit execution through `run()` is refused unless preflight succeeds.

## Current compose file

`docker/docker-compose.grfics.yml` is retained as an integration scaffold.

Its existence is **not evidence** that a GRFICS/OpenPLC experiment was run.

The current repository configuration must not be described as a completed
full-GRFICS deployment. Full GRFICS environments may require host networking,
macvlan configuration, a suitable physical/virtual interface, sufficient RAM,
and additional upstream components.

## Evidence boundary

Repository unit tests mock Docker and host prerequisites.

They verify adapter behavior only. They do not constitute evidence of:

- a running PLC;
- a running GRFICS process simulation;
- a successful macvlan deployment;
- captured production traffic;
- real-world validation;
- completed laboratory experiments.

Generated PCAP fixtures remain explicitly classified as sanitized fixtures.

## External milestone

A future lab milestone may include:

1. selecting an isolated authorized host;
2. installing Docker and Docker Compose;
3. documenting the host NIC and macvlan topology;
4. confirming available RAM and storage;
5. pinning an upstream GRFICS/OpenPLC revision;
6. running the preflight;
7. launching the isolated laboratory;
8. passively capturing traffic;
9. recording hashes, timestamps, tool versions, topology, and provenance;
10. publishing only reproducible measured results.

Until those steps are actually performed and recorded, OTShield must not claim
completed GRFICS/OpenPLC experimental validation.

## Safety

The implemented benchmark path is defensive and passive.

The simulation adapter does not scan external systems, exploit devices, inject
packets, discover credentials, or manipulate production PLCs. Any future active
research must be separately authorized and confined to an isolated laboratory.
