# OTShield Bench: Paired Timing-Detector Evaluation Under Degraded Connectivity

**Technical Report — v0.6 working-branch post-release update**
**Author:** Jayachandra Reddy Palle  
**Date:** September 22, 2026  
**Branch:** `research/v0.6-experiments`  
**Execution commit:** `88e1f056dc2143129ef115f3ce1ad731fd0e9a0e`
**License:** Apache-2.0  
**Archived v0.6.0-alpha DOI:** 10.5281/zenodo.22899466 (archive predates the post-release study below)

## Abstract

OTShield Bench is a reproducible, vendor-neutral benchmark for detection
effectiveness, resource cost, and resilience under degraded connectivity. This
report evaluates a fixed 50 ms timing threshold against an independently
calibrated robust threshold on identical isolated OpenPLC captures. The completed
study comprises 25 trials across five conditions: 125 condition runs, 7,500 planned
read-only Modbus/TCP transactions, and 250 detector evaluations. Both detectors
achieved mean recall/F1 of 1.0/1.0 in clean and 20 ms delay conditions, and
0.97/0.984561403508772 under 20 ms delay, 5 ms jitter, and 5% loss. Under 40 ms
delay and 10 ms jitter, robust-minus-baseline recall improved by 0.572; under
60 ms delay and 10 ms jitter, it improved by 1.0. Observation coverage was 1.0
and false positives were zero throughout. These are controlled laboratory
measurements, with no production or external-validation claim.

## 1. Research Question and Contributions

How does degraded network connectivity affect a fixed-threshold OT timing
detector compared with a threshold independently calibrated from historical
clean laboratory evidence? The [predeclared protocol](v0.6_experiment_protocol.md)
fixes calibration, traffic, conditions, trial count, metrics, and analysis.

The principal contribution is benchmark methodology: paired evaluation of the
same captured observations, independently frozen calibration, explicit ground
truth, run-level uncertainty, resource instrumentation, and preserved provenance
and failures. The v0.6 study extends the historical five-trial v0.5 study to
25 trials per condition and adds a second detector without presenting OTShield
as a generic IDS product. OTB-SCENARIO, OTB-TELEMETRY, OTB-DETECT, and OTB-EVAL
remain the benchmark abstractions.

## 2. Evidence Boundary and Architecture

Results come exclusively from
[the completed replacement study](../evidence/v06/20260922T174026Z/).
[aggregate.json](../evidence/v06/20260922T174026Z/aggregate.json) is the source of
truth for all numerical results; [study.json](../evidence/v06/20260922T174026Z/study.json)
records completion. Synthetic and mocked regression tests verify software behavior
and are not laboratory measurements. The lab uses a GRFICS-derived OpenPLC image;
it is not a completed full GRFICSv3 process simulation.

Each run retains raw capture, protocol, normalized telemetry, provenance,
normalization metadata, paired observations/results, and SHA-256 integrity files.
The study adds `OTB-V06-STUDY/0.1`, `OTB-V06-AGGREGATE/0.1`, and
`OTB-V06-CALIBRATION/0.1` records while retaining existing ingestion, telemetry,
result, and resilience protocol/observation schemas. The
[release manifest](v0.6_release_manifest.md) inventories them.

## 3. Calibration and Paired Detector Method

The unchanged baseline `polling-burst-v1` alerts for
`0 < observed_interval_ms < 50.0`. The robust detector
`robust-polling-burst-v1` uses the same strict inequality with its frozen threshold.
Only historical v0.5 clean observations from
`evidence/repeatability/20260920T182506Z/` that are matched, explicitly normal,
and have positive finite intervals are eligible. Controlled-burst observations
and all v0.6 test observations are excluded from calibration.

For eligible intervals x, M = median(x), MAD = median(abs(x − M)),
robust sigma = 1.4826 × MAD, and threshold = M − 3.5 × robust sigma.
The [frozen calibration](v0.6_calibration.json) records 195 samples (39 from each
of five clean runs), M = 101.010009765625 ms, MAD = 0.14892578125 ms,
robust sigma = 0.22079736328125 ms, and threshold = 100.23721899414062 ms.
At least 30 eligible samples and finite positive MAD are required; invalid
calibration fails closed. Historical file hashes and source commits are retained.
The frozen JSON SHA-256 is
`d8676d4670ba44c0f4b1045e5e07dd2d251ccb4a63ed8089b9b9aada729ea234`.

Each detector evaluates the same normalized capture and canonical observation
view per condition. Detector inputs have labels cleared; ground truth belongs to
the evaluation layer. The second detector does not cause a second capture.
Neither per-run protocols nor test traffic can override the pinned calibration.

## 4. Laboratory Setup and Ground Truth

The isolated Docker-based OpenPLC laboratory applies Linux `tc netem` impairment
on client egress and captures in the OpenPLC/server network namespace. Recorded
provenance includes Python 3.14.4, Docker 29.8.1, Compose v5.5.1, and Linux kernel
6.18.33.2-microsoft-standard-WSL2. The configured image is
`fortiphyd/grfics-plc:latest`, with recorded image ID
`sha256:364461af6d7b56563fa6fdc6a296a2dfa6530caf07ea736bbc9a71701a360919`.
The mutable image tag alone is insufficient to reproduce the environment; use
the retained image identity and per-run provenance. Host CPU/RAM specifications
are not established by these provenance fields.

| Condition | Delay | Jitter | Loss |
| --- | ---: | ---: | ---: |
| clean | 0 ms | 0 ms | 0% |
| delay20 | 20 ms | 0 ms | 0% |
| delay20_jitter5_loss5 | 20 ms | 5 ms | 5% |
| delay40_jitter10 | 40 ms | 10 ms | 0% |
| delay60_jitter10 | 60 ms | 10 ms | 0% |

Every condition plans 60 bounded read-only Modbus/TCP Function Code 3 transactions:
1–20 normal-pre, 21–40 controlled-burst, and 41–60 normal-post. Normal spacing is
approximately 100 ms and burst spacing approximately 10 ms. The middle 20
transactions are labeled anomalous by the protocol, never by detector output.
The first interval is unavailable rather than a measured zero. No production
PLC manipulation is part of this experiment. One OpenPLC instance serves all
five conditions in each trial, with restart between trials. Condition order
rotates deterministically across trials.

## 5. Statistical Method

For each detector and condition, the aggregate reports N, arithmetic mean,
sample standard deviation, minimum, maximum, and two-sided 95% Student-t
intervals over run-level metrics. For N = 25 the interval is
mean ± t(0.975, 24) × SD / sqrt(25). Paired effects are calculated within each
run as robust minus baseline, then summarized across the 25 paired differences.
These are absolute metric differences, not relative percentages or standardized
effect sizes. Intervals in this report and JSON are unbounded mathematical
intervals. No multiplicity-adjusted or population-wide claim is made.

Primary metrics are recall, F1, coverage, and end-to-end recall. Coverage measures
observed planned transactions; end-to-end recall accounts for planned anomalies.
Precision, confusion counts, CPU time, wall time, and traced peak memory are also
retained. Mean F1 is the mean of run-level F1 values, not F1 recomputed from mean
recall. Runs, not the 7,500 transactions, are the units of interval estimation.
Repeated measurements on one lab host do not establish independence across sites.

## 6. Readiness, Infrastructure Hardening, and Errata

The separate `scripts/v06_lab_readiness.py` gate checks dependencies, Docker/Compose,
images, writable paths, disk space, networking, and lock availability. Explicitly
authorized startup enables bounded TCP/FC3 readiness probing with container
identity checks and cleanup of owned resources. Its status reports are operational
checks, not scientific evidence; it does not start the study or create results.
It is distinct from the runner's evidence-free dry-run and per-trial readiness wait.

The runner holds a nonblocking advisory host lock through worker termination,
cleanup, and accounting. The worker verifies inherited ownership before cleanup.
Container identity and running-state checks at condition lifecycle boundaries
fail closed on missing, stopped, or replaced OpenPLC instances, without automatic
repair or retry. The lock covers cooperating runners in this checkout; it cannot
prevent unrelated Docker commands or interference between checks.

Two earlier attempts remain preserved and excluded from the final aggregate:

- Study A, `evidence/v06/20260920T203716Z`, stopped at `trial-7/clean` on duplicate
  TID 60. A delayed response-only retransmission from a previous connection was
  retained alongside the current matched transaction. The
  [duplicate-TID erratum](v0.6_duplicate_tid_erratum.md) documents the transport-only
  canonicalization rule `v06-earlier-foreign-response-only-v1`. Only the narrowly
  qualifying earlier foreign response is excluded from the evaluation view;
  ambiguous duplicates fail closed. Original normalization stays unchanged, both
  detectors share the view, and additive audit metadata preserves the decision.
- Study B, `evidence/v06/20260920T211629Z`, completed 1/125 runs before the next
  condition failed because OpenPLC no longer existed. The
  [infrastructure erratum](v0.6_study_b_infrastructure_erratum.md) records events
  consistent with host-side lifecycle/cleanup interference. The responsible process
  was not identified; detector output did not cause the failure.

These post-failure corrections did not tune thresholds, replace historical
calibration, or change the predeclared design and statistical method. Partial
results are not pooled with the replacement study, and unfavorable completed
replacement results are not excluded.

## 7. Completed Replacement Study and Results

Study `20260922T174026Z` reports `completed`: 25 trials × 5 conditions = 125
completed condition runs, 60 planned transactions/run, 7,500 planned transactions,
and 250 detector evaluations. It records no failed attempts, unattempted runs,
or infrastructure failure within this replacement root. That accounting does not
erase the earlier failed studies. Execution commit is
`88e1f056dc2143129ef115f3ce1ad731fd0e9a0e`; the immutable study-evidence milestone is
`340386e9783f450ccf7b30c84557901d87402c90`.

### 7.1 Effectiveness

Every table row summarizes 25 runs per detector. Values below are taken directly
from the aggregate.

| Condition | Baseline recall | Baseline F1 | Robust recall | Robust F1 |
| --- | ---: | ---: | ---: | ---: |
| clean | 1.0 | 1.0 | 1.0 | 1.0 |
| delay20 | 1.0 | 1.0 | 1.0 | 1.0 |
| delay20_jitter5_loss5 | 0.97 | 0.984561403508772 | 0.97 | 0.984561403508772 |
| delay40_jitter10 | 0.428 | 0.5912675775590125 | 1.0 | 1.0 |
| delay60_jitter10 | 0.0 | 0.0 | 1.0 | 1.0 |

Coverage is 1.0 in every run for both detectors; end-to-end recall equals recall.
False positives are zero in every run. Precision is 1.0 where detections occur;
the baseline at `delay60_jitter10` makes no detections and records precision 0.0,
which does not indicate false positives. At that condition each baseline run has
TP = 0, FN = 20; each robust run has TP = 20, FN = 0. Both have TN = 40, FP = 0.

### 7.2 Paired Effect Sizes

Each effect has N = 25. Intervals and means retain the aggregate's precision.

| Condition | Metric | Mean robust − baseline | SD | 95% CI low | 95% CI high |
| --- | --- | ---: | ---: | ---: | ---: |
| clean | recall | 0.0 | 0.0 | 0.0 | 0.0 |
| clean | f1 | 0.0 | 0.0 | 0.0 | 0.0 |
| delay20 | recall | 0.0 | 0.0 | 0.0 | 0.0 |
| delay20 | f1 | 0.0 | 0.0 | 0.0 | 0.0 |
| delay20_jitter5_loss5 | recall | 0.0 | 0.0 | 0.0 | 0.0 |
| delay20_jitter5_loss5 | f1 | 0.0 | 0.0 | 0.0 | 0.0 |
| delay40_jitter10 | recall | 0.572 | 0.1109429282709508 | 0.5262050099837566 | 0.6177949900162433 |
| delay40_jitter10 | f1 | 0.4087324224409875 | 0.11009074249538149 | 0.3632891974240317 | 0.4541756474579433 |
| delay60_jitter10 | recall | 1.0 | 0.0 | 1.0 | 1.0 |
| delay60_jitter10 | f1 | 1.0 | 0.0 | 1.0 | 1.0 |

The 40 ms delay condition shows +0.572 recall (57.2 percentage points) and
+0.4087324224409875 F1. At 60 ms delay both improvements are +1.0. Zero-width
intervals reflect zero observed variation in these runs, not certainty beyond
the tested setting. Clean and lighter conditions show zero paired recall/F1 effect.

### 7.3 Resource Measurements

Per-condition means below are baseline / robust, rounded to six decimal places.
N = 25 per detector and condition; full SD, min/max, and intervals remain in the
aggregate.

| Condition | CPU time (ms) | Wall time (ms) | Peak traced memory (`peak_memory_mb`) |
| --- | ---: | ---: | ---: |
| clean | 0.225126 / 0.200725 | 0.248112 / 0.221291 | 0.010994 / 0.007469 |
| delay20 | 0.181945 / 0.200659 | 0.200574 / 0.222860 | 0.010994 / 0.007469 |
| delay20_jitter5_loss5 | 0.209775 / 0.144973 | 0.230637 / 0.167376 | 0.010994 / 0.007469 |
| delay40_jitter10 | 0.178405 / 0.180525 | 0.196683 / 0.203694 | 0.010994 / 0.007469 |
| delay60_jitter10 | 0.201605 / 0.151400 | 0.222166 / 0.176600 | 0.010994 / 0.007469 |

Instrumentation surrounds detector prediction. Memory is Python `tracemalloc`
peak allocation divided by 1024 squared (MiB despite the field name), not total
process or system memory. These small host-specific measurements omit capture,
parsing, calibration, container costs, and the full deployment pipeline. They do
not establish production throughput or a general robust-detector efficiency advantage.


### 7.4 Relationship to the archived v0.6.0-alpha study

The archived v0.6.0-alpha evidence at `20260922T021855Z` reported the same
qualitative pattern but slightly different run-level means. It reported mean
recall 0.95 for both detectors under `delay20_jitter5_loss5` and baseline mean
recall 0.46 under `delay40_jitter10`; the post-release study reports 0.97 and
0.428, respectively. This is an internal repeat execution on the same
laboratory family, not an external replication.

## 8. Interpretation

Within the documented isolated OpenPLC lab and preregistered timing setup, the
independently calibrated robust threshold showed materially greater resilience
under the heavier tested delay conditions, with no observed recall/F1 penalty
under clean and lighter tested conditions.

Complete transaction visibility did not prevent the fixed threshold from missing
bursts under heavier impairment. The comparison is consistent with a broader
independently selected timing threshold tolerating this setup's altered observed
intervals. The combined jitter/loss condition still reduces both detectors'
recall equally; robust calibration does not eliminate every impairment effect.
The benchmark measures this conditional behavior rather than ranking all OT
security products.

## 9. Limitations and Threats to Validity

Evidence is limited to one isolated OpenPLC setup, read-only Modbus/TCP FC3,
a fixed transaction schedule, two closely related timing rules, five client-egress
impairments, and server-side capture. Historical clean calibration is independent
of test data but remains from the same laboratory family; transfer to other
polling rates and hosts is untested. Rotation reduces fixed-order effects without
establishing site-level independence. Student-t intervals for bounded metrics
are descriptive and do not cover untested environments. Zero observed false
positives does not prove a universally zero false-positive rate.

The post-failure canonicalization and lifecycle corrections are disclosed, not
hidden as an uninterrupted first attempt. The image tag is mutable, external
packages/images may become unavailable, and host resource specifications are
incomplete for cross-machine cost comparison. This report claims no production
validation, universal superiority, DNP3 or EtherNet/IP validation, full GRFICS
validation, external replication, industry adoption, or standards compliance.

## 10. Reproducibility

Use the [manifest](v0.6_release_manifest.md), retained
[execution record](../evidence/v06/20260922T174026Z/execution.json), copied protocol,
frozen calibration, per-run provenance, and study integrity inventory to audit
this report. The execution commit identifies the experimental implementation;
it is distinct from later findings and release-documentation changes.

Read-only evidence verification, from the repository root:

```sh
(cd evidence/v06/20260922T174026Z && sha256sum -c STUDY_SHA256SUMS)
```

Software validation in the installed development environment:

```sh
python -m pytest -q
python -m build
git diff --check
./scripts/verify_release.sh
```

These software checks do not launch a laboratory study. The runner's
`python scripts/run_v06_study.py --dry-run` validates the frozen calibration and
shows the schedule without contacting Docker or creating output. Future collection
requires a separately authorized isolated laboratory, clean execution checkout,
new output root, and the procedure in [implementation notes](v0.6_implementation.md).
Do not overwrite retained evidence or retune calibration using v0.6 results.
See also [reproducibility guidance](../docs/reproducibility.md).
The original v0.6.0-alpha release remains published on
[GitHub](https://github.com/ASHTHRA/otshield-bench/releases/tag/v0.6.0-alpha)
and archived on [Zenodo](https://doi.org/10.5281/zenodo.22899466). That archive predates the post-release study documented here and is not being rewritten.

## 11. Critical-Infrastructure Relevance

For defensive monitoring of critical-infrastructure OT, visibility and detector
effectiveness are distinct measurement questions. This study provides a bounded
example of why connectivity conditions, ground truth, capture location, and cost
must accompany a detection score. Its methodology can inform laboratory evaluation
plans; these results do not establish operational readiness, process safety,
regulatory compliance, or effectiveness at an infrastructure site.

## 12. Future Work

Priorities are independent replication of the Modbus milestone, additional hosts
and polling schedules, other capture points and impairment models, fuller resource
measurement, and explicitly versioned protocols for new detector comparisons.
Full process-simulation evaluation remains future work. Defer DNP3 and EtherNet/IP
expansion until the Modbus milestone is stable.

## 13. Conclusion

The completed paired study supports greater robust-threshold resilience under the
two heavier tested delay conditions, with equal recall/F1 in the other conditions.
The contribution is the reproducible, evidence-preserving comparison connecting
calibration, observation conditions, ground truth, paired effects, resource
measurements, and failure disclosure within a clearly bounded laboratory scope.

## References

1. Palle, J. R., [v0.6 Predeclared Experiment Protocol](v0.6_experiment_protocol.md).
2. OTShield Bench, [completed study manifest](../evidence/v06/20260922T174026Z/study.json)
   and [aggregate statistics](../evidence/v06/20260922T174026Z/aggregate.json), 2026.
3. OTShield Bench, [frozen calibration](v0.6_calibration.json) and
   [implementation notes](v0.6_implementation.md).
4. OTShield Bench, [duplicate-TID erratum](v0.6_duplicate_tid_erratum.md) and
   [Study B infrastructure erratum](v0.6_study_b_infrastructure_erratum.md).
5. Palle, J. R., [v0.5 Technical Report](OTShield_Bench_v0.5_Technical_Report.md),
   historical methodological context; its numerical results are not pooled here.
6. OTShield Bench, [v0.6 Findings](v0.6_findings.md), findings commit `932dab1`.
