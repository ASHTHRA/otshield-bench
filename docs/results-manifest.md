# OTB-RESULT/0.1 Benchmark Result Manifest

OTShield benchmark outputs use a versioned result manifest so a reported score
can be interpreted together with its detector, protocol, provenance,
environment, resource measurements, and degraded-connectivity configuration.

## Schema

Current schema:

`OTB-RESULT/0.1`

A manifest records:

- benchmark version;
- detector adapter;
- protocol;
- deterministic seed;
- dataset provenance;
- execution environment metadata;
- effectiveness metrics;
- measured resource-cost metrics;
- degraded-connectivity settings.

## Effectiveness

The manifest preserves the metrics returned by OTShield's existing evaluator:

- total;
- observed;
- dropped;
- coverage;
- TP / FP / FN / TN;
- precision;
- recall;
- F1;
- false-positive rate;
- end-to-end recall.

The manifest does not recompute or silently change these values.

## Resource cost

The bounded v0.3 schema provides fields for:

- wall-clock time in milliseconds;
- CPU time in milliseconds;
- peak memory in megabytes.

A value of `null` explicitly means **not measured**.

OTShield must not replace an unmeasured metric with an assumed, estimated, or
invented number.

## Degraded connectivity

Each result records the configured observation degradation:

- packet/event loss ratio;
- added latency;
- jitter.

This allows effectiveness results to be compared under reproducible degradation
settings.

## Provenance

Provenance contains at minimum:

- `source`
- `dataset_id`
- `evidence_type`

Synthetic examples must remain explicitly identified as synthetic.

Sanitized PCAP fixtures are not real laboratory captures.

## Determinism

For identical manifest input, JSON serialization and Markdown report generation
are deterministic.

JSON is serialized with sorted keys and non-finite values are rejected.

## Synthetic example

The repository tests construct a result from OTShield's deterministic synthetic
`value_spike` scenario and the `rules-v1` detector.

The example uses:

- source: `synthetic`;
- evidence type: `synthetic`;
- protocol: `modbus-tcp`;
- seed: `42`.

Resource-cost values in that example are left `null` unless they were actually
measured.

No synthetic example is represented as a GRFICS/OpenPLC laboratory result or
real-world validation.
