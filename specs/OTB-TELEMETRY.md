# OTB-TELEMETRY/0.1

Each event is a JSON object with the following required fields. Unknown constructor
fields are rejected. Numeric values must be finite; JSON NaN/Infinity are invalid.

| Field | Meaning |
| --- | --- |
| schema | `OTB-TELEMETRY/0.1` |
| event_id | Nonempty identity, unique within a scenario run |
| timestamp_ms | Nonnegative synthetic source time, or arrival time after faults |
| function_code | Integer 1–127; abstract Modbus function |
| address | Integer register address 0–65535 |
| value | Finite synthetic process value; not a raw register encoding |
| interval_ms | Nonnegative source polling interval, retained after loss |
| latency_ms | Nonnegative synthetic transaction latency plus injected delay |
| label | Boolean anomaly ground truth; excluded from detector features |

The truth stream is immutable. Independent seeded Bernoulli loss in [0,1] removes
observations. Survivors receive delay `latency_ms + Uniform(0,jitter_ms)`; both
parameters must be nonnegative and finite. Delay is added to timestamp and latency.
Survivors are sorted by `(timestamp_ms,event_id)` to represent arrival reordering.
Existing baseline latency is not added to source timestamp. This is an abstract
observation fault model, not TCP retransmission or physical process simulation.
