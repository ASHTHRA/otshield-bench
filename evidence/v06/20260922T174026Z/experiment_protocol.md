# OTShield Bench v0.6 Predeclared Experiment Protocol

## Status

Predeclared before implementation and before collection of v0.6 experimental results.

This document defines the v0.6 experimental design. Material changes to the
detectors, calibration procedure, test conditions, trial count, primary metrics,
or analysis method after v0.6 results are observed require a new protocol
revision and must not silently replace this protocol.

## 1. Research Question

How does degraded network connectivity affect a fixed-threshold OT timing
detector compared with a detector whose threshold is independently calibrated
from historical clean laboratory evidence?

The experiment evaluates detector behavior under identical captured traffic so
that detector comparisons are paired by trial and network condition.

## 2. Evidence Boundary

The experiment uses an isolated OpenPLC laboratory and bounded read-only
Modbus/TCP Function Code 3 traffic.

It does not claim:

- production OT validation;
- universal cybersecurity effectiveness;
- completed full GRFICSv3 process-simulation validation;
- DNP3 experimental validation;
- EtherNet/IP experimental validation;
- industry adoption;
- independent external replication.

## 3. Baseline Detector

Detector:

    polling-burst-v1

The existing detector remains unchanged.

Decision rule:

    alert when observed_interval_ms > 0
    and observed_interval_ms < 50.0 ms

The 50 ms threshold must not be changed using v0.6 results.

## 4. Independently Calibrated Detector

Provisional detector name:

    robust-polling-burst-v1

Calibration data must come only from the already-existing v0.5 OpenPLC
repeatability evidence:

    evidence/repeatability/20260920T182506Z/

Only observations satisfying all of the following may be used for calibration:

- condition is clean;
- expected_anomaly is false;
- transport status is matched;
- observed_interval_ms is present and positive.

Controlled-burst/anomalous observations must not be included in calibration.

The calibration procedure is fixed before v0.6 testing.

For the eligible historical normal intervals x:

    M = median(x)
    MAD = median(abs(x - M))
    robust_sigma = 1.4826 * MAD
    threshold = M - (3.5 * robust_sigma)

The detector alerts when:

    observed_interval_ms > 0
    and observed_interval_ms < threshold

Calibration must fail closed if there are insufficient eligible observations,
if MAD is non-finite, or if MAD <= 0. No v0.6 test observations may be used to
repair, tune, or replace the calibration threshold.

The calibration source files, source commit, source hashes, calculated median,
MAD, robust sigma, and final threshold must be recorded in machine-readable
evidence.

## 5. Test Conditions

The same five network conditions used for the v0.5 study will be retained:

| Condition | Delay | Jitter | Loss |
|---|---:|---:|---:|
| clean | 0 ms | 0 ms | 0% |
| delay20 | 20 ms | 0 ms | 0% |
| delay20_jitter5_loss5 | 20 ms | 5 ms | 5% |
| delay40_jitter10 | 40 ms | 10 ms | 0% |
| delay60_jitter10 | 60 ms | 10 ms | 0% |

Impairment remains on client egress.

Packet capture remains at the OpenPLC/server network namespace.

## 6. Trial Count

Predeclared trial count:

    25 trials per condition

Five conditions produce:

    125 completed condition runs

Each condition contains:

    60 planned Modbus/TCP transactions

Total planned transactions:

    7,500

Condition order must rotate between trials using the same deterministic approach
used by the v0.5 repeatability runner.

## 7. Ground Truth

Each condition retains the existing 60-transaction schedule:

- transactions 1-20: normal-pre;
- transactions 21-40: controlled-burst;
- transactions 41-60: normal-post.

Normal planned spacing:

    approximately 100 ms

Controlled-burst planned spacing:

    approximately 10 ms

Ground truth is determined from the predeclared transaction protocol and never
from detector output.

## 8. Paired Evaluation

Both detectors must evaluate the same normalized capture from each condition
run.

No separate network capture may be generated for the second detector.

This creates a paired comparison in which network traffic, ground truth,
capture point, and impairment condition are identical for both detectors.

## 9. Primary Metrics

Primary metrics:

- recall;
- F1;
- observation coverage;
- end-to-end recall.

Additional recorded metrics:

- precision;
- false positives;
- false negatives;
- true positives;
- true negatives;
- wall-clock evaluation time;
- CPU evaluation time;
- peak evaluation memory.

## 10. Statistical Analysis

For every detector and condition, report:

- N;
- arithmetic mean;
- sample standard deviation;
- minimum;
- maximum;
- two-sided 95% Student-t interval over run-level metrics.

Because the two detectors evaluate identical captures, also calculate
per-run paired differences:

    robust-polling-burst-v1 metric
    minus
    polling-burst-v1 metric

For the paired difference in recall and F1, report:

- N;
- mean paired difference;
- sample standard deviation;
- two-sided 95% Student-t interval.

Probability metric display intervals may be clipped to [0,1], but mathematical
unbounded intervals must remain available in machine-readable evidence.

No detector will be declared universally superior based on this experiment.

## 11. Failed or Incomplete Runs

The benchmark must fail closed when required evidence is missing or malformed.

A condition run is not considered completed unless its expected protocol,
capture, normalization, observations, detector results, provenance, and
integrity information are produced successfully.

Failed attempts must not be silently discarded to improve reported metrics.

If an infrastructure failure requires repetition, the reason must be documented
and the final study manifest must distinguish completed runs from failed
attempts where technically possible.

No run may be excluded solely because its detector result is unfavorable.

## 12. Integrity and Provenance

For each completed run retain, at minimum:

- raw PCAP;
- protocol;
- normalized telemetry;
- provenance;
- normalization metadata;
- observations;
- baseline detector result;
- calibrated detector result;
- integrity hashes.

The study level must retain:

- calibration evidence;
- aggregate statistics;
- paired comparison statistics;
- study manifest;
- study-level SHA-256 hashes;
- execution Git commit.

## 13. Stop Rule

No detector threshold, test condition, ground-truth rule, or primary statistical
method may be modified after inspecting v0.6 results without creating a new,
explicitly versioned experiment protocol.

## 14. Intended Interpretation

The experiment is designed to determine whether an independently calibrated
robust timing threshold exhibits different resilience behavior from the existing
fixed 50 ms threshold under the documented isolated OpenPLC network conditions.

Any conclusions apply only to the documented traffic, detectors, laboratory,
capture point, network impairment model, and experimental conditions.
