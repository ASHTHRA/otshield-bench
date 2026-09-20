# OTShield OpenPLC Lab Baseline

- Schema: `OTB-LAB-BASELINE/0.1`
- Dataset: `openplc-readonly-20260920T171404Z`
- Source: `grfics`
- Evidence type: `lab_capture`

## Transaction integrity

- Total transactions: `20`
- Matched transactions: `20`
- Matched ratio: `1.000000`
- Duplicate packets: `0`

## Protocol coverage

- Protocol: `modbus-tcp`
- Function-code counts: `{"3": 20}`
- Address counts: `{"0": 2, "1": 2, "2": 2, "3": 2, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 2}`

## Response latency

- Minimum: `0.199951 ms`
- Mean: `4.873743 ms`
- Median (p50): `0.320435 ms`
- p95: `5.107849 ms`
- Maximum: `91.103027 ms`

## Inter-request interval

- Samples: `19`
- Minimum: `100.697021 ms`
- Mean: `105.770315 ms`
- Median (p50): `100.976074 ms`
- p95: `110.439087 ms`
- Maximum: `192.062012 ms`

The first transaction has no preceding request, so its interval is not included.

## Evidence interpretation

This is a descriptive baseline from a real isolated OpenPLC capture.
It is not an anomaly-detector effectiveness result.

## Limitations

- single short capture
- read-only Function Code 3 traffic
- normal baseline only; no anomaly-effectiveness measurement
- first transaction may include connection/container warm-up cost
- not a full GRFICSv3 process-simulation experiment
