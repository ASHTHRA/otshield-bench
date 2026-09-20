# OTShield Benchmark Result

- Schema: `OTB-RESULT/0.1`
- Benchmark version: `0.4.0-alpha`
- Detector adapter: `polling-burst-v1`
- Protocol: `modbus-tcp-readonly-timing`
- Seed: `0`

## Provenance

- dataset_id: `openplc-repeat-20260920T182506Z-t02-delay20_jitter5_loss5`
- evidence_type: `lab_capture`
- source: `grfics`

## Environment

- experiment_protocol_schema: `OTB-LAB-RESILIENCE-PROTOCOL/0.1`
- experiment_protocol_sha256: `d5efd926b6d349ce156b91c7b96e84ce30040368600adfe4dd2d19bacb08899f`
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
- tp: `20`
- fp: `0`
- fn: `0`
- tn: `40`
- precision: `1.0`
- recall: `1.0`
- f1: `1.0`
- false_positive_rate: `0.0`
- end_to_end_recall: `1.0`

## Resource cost

- wall_time_ms: `0.172513`
- cpu_time_ms: `0.158618`
- peak_memory_mb: `0.01099395751953125`

## Degraded connectivity

- loss: `0.05`
- latency_ms: `20.0`
- jitter_ms: `5.0`
