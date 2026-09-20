# OTShield Benchmark Result

- Schema: `OTB-RESULT/0.1`
- Benchmark version: `0.4.0-alpha`
- Detector adapter: `polling-burst-v1`
- Protocol: `modbus-tcp-readonly-timing`
- Seed: `0`

## Provenance

- dataset_id: `openplc-repeat-20260920T182506Z-t01-delay60_jitter10`
- evidence_type: `lab_capture`
- source: `grfics`

## Environment

- experiment_protocol_schema: `OTB-LAB-RESILIENCE-PROTOCOL/0.1`
- experiment_protocol_sha256: `7f66c9fd3316dc7e104c2e46fac92cf16108c09d03d1186e0bb8da80003cd633`
- impairment_direction: `client-egress`
- label_source: `predeclared transaction-id experiment protocol`
- platform: `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43`
- python: `3.14.4`
- sample_count: `60`
- threshold_ms: `50.0`

## Effectiveness

- total: `60`
- observed: `60`
- dropped: `0`
- coverage: `1.0`
- tp: `0`
- fp: `0`
- fn: `20`
- tn: `40`
- precision: `0.0`
- recall: `0.0`
- f1: `0.0`
- false_positive_rate: `0.0`
- end_to_end_recall: `0.0`

## Resource cost

- wall_time_ms: `0.140768`
- cpu_time_ms: `0.128236`
- peak_memory_mb: `0.01099395751953125`

## Degraded connectivity

- loss: `0.0`
- latency_ms: `60.0`
- jitter_ms: `10.0`
