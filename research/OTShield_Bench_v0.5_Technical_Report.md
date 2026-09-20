# OTShield Bench: A Reproducible, Vendor-Neutral Benchmark for OT Cyber-Detection Effectiveness and Resilience Under Degraded Connectivity

**Technical Report - v0.5.0-alpha**  
**Author:** Jayachandra Reddy Palle  
**Date:** September 20, 2026  
**Software release:** https://github.com/ASHTHRA/otshield-bench/releases/tag/v0.5.0-alpha  
**Archived citation release:** OTShield Bench v0.5.1-alpha — https://doi.org/10.5281/zenodo.22863660  
**Release commit:** `8f79f77f6a410d4c648ca7dbddd3e1b5a4148edb`  
**License:** Apache-2.0

## Abstract

Operational technology (OT) cyber-detection tools are often discussed in terms of whether they detect a known event, but operational deployment also depends on whether detection remains reliable when the observation path is delayed, jittered, lossy, or resource-constrained. OTShield Bench is an open, vendor-neutral benchmarking framework that separates three questions: detection effectiveness, deployment resource cost, and resilience under degraded connectivity. The v0.5.0-alpha release combines deterministic synthetic scenarios with measured evidence from an isolated OpenPLC laboratory. The laboratory path uses bounded read-only Modbus/TCP Function Code 3 traffic, server-side packet capture, transaction-aware normalization, predeclared ground truth, explicit provenance, and SHA-256 integrity records.

A five-trial repeatability study evaluated a fixed 50 ms polling-burst threshold across five client-egress network conditions. Observation coverage remained 1.000 in all 25 condition runs, while mean recall fell from 1.000 in clean and +20 ms-delay conditions to 0.950 with +20 ms delay, 5 ms jitter, and 5% loss; 0.420 with +40 ms delay and 10 ms jitter; and 0.000 with +60 ms delay and 10 ms jitter. The result demonstrates, for this controlled detector and laboratory configuration, that network-path degradation can reduce timing-based detector effectiveness even when application-layer transaction visibility remains complete. These measurements are laboratory evidence, not claims of production OT performance, full GRFICSv3 validation, universal cybersecurity effectiveness, or independent external replication.

## 1. Motivation and Context

OT systems support industrial and critical-infrastructure processes with distinctive reliability, safety, latency, and availability constraints. NIST SP 800-82 Rev. 3 emphasizes that OT security must account for these operational characteristics, not only conventional information-security controls [1]. CISA's Cross-Sector Cybersecurity Performance Goals likewise frame measurable cybersecurity practices as relevant across critical-infrastructure owners and operators, including OT environments [2].

Existing detection evaluations can be valuable for measuring whether products observe adversary behaviors. For example, MITRE Engenuity has published ATT&CK Evaluations for Industrial Control Systems that examine detection of ICS-focused adversary behavior [3]. OTShield Bench addresses a narrower and complementary research question: once a detection method depends on observed OT telemetry, how does measured effectiveness change when the network path or observation environment is degraded?

The benchmark therefore treats resilience as a first-class measurement dimension rather than assuming that detector performance under ideal connectivity transfers unchanged to impaired conditions.

## 2. Benchmark Objective

OTShield Bench is designed to support reproducible comparison along three dimensions:

1. **Detection effectiveness** - precision, recall, F1, false-positive rate, observation coverage, and end-to-end recall.
2. **Deployment resource cost** - measured wall time, CPU time, and peak memory where those values are actually observed; unavailable values remain explicitly unmeasured.
3. **Resilience under degraded connectivity** - changes in measured effectiveness under controlled delay, jitter, and loss settings.

The benchmark is intentionally evidence-oriented. Synthetic fixtures, sanitized fixtures, and laboratory captures are classified separately. A software feature is not represented as experimental validation merely because a test or integration scaffold exists.

## 3. Architecture and Evidence Model

The v0.5 workflow uses a predeclared experiment protocol, bounded read-only traffic, packet capture at the OpenPLC/server network namespace, transaction-aware normalization, detector execution, evaluation, and evidence manifests. Each laboratory run preserves raw PCAP data, normalized telemetry, provenance, protocol metadata, observations, result manifests, and SHA-256 checksums.

The core schema family includes `OTB-TELEMETRY/0.1`, `OTB-INGEST/0.1`, `OTB-RESULT/0.1`, `OTB-LAB-EVIDENCE/0.1`, `OTB-NORMALIZATION-EVIDENCE/0.1`, `OTB-LAB-TIMING-PROTOCOL/0.1`, `OTB-LAB-TIMING-OBSERVATIONS/0.1`, `OTB-LAB-RESILIENCE-PROTOCOL/0.1`, `OTB-LAB-RESILIENCE-OBSERVATIONS/0.1`, and `OTB-RESILIENCE-REPLICATES/0.1`.

### 3.1 Evidence separation

The project maintains explicit boundaries between:

- deterministic synthetic benchmark data;
- sanitized fixtures used for parser and regression testing;
- isolated OpenPLC laboratory captures;
- future full-GRFICS or external laboratory evidence;
- production or independently reproduced evidence, which is not yet claimed.

This separation is important because benchmark credibility depends on the traceability of each result to its actual source and execution environment.

## 4. Laboratory Method

### 4.1 Environment

The current measured evidence uses a minimal isolated Docker-based OpenPLC environment derived from the configured GRFICS PLC image. The recorded environment includes Docker and Docker Compose versions, Linux kernel version, Python version, image identifier, capture-time Git commit, and traffic policy. The current evidence must not be described as a completed full GRFICSv3 process simulation.

### 4.2 Traffic policy

The repeatability experiments generate only Modbus/TCP Function Code 3 read-holding-register requests against addresses 0 through 9. No write commands, register scans, credential discovery, external target scanning, or production PLC manipulation are part of the experiment.

Each condition has 60 predeclared transactions:

- transactions 1-20: normal-pre phase, approximately 100 ms planned spacing;
- transactions 21-40: controlled-burst phase, approximately 10 ms planned spacing, labeled anomalous;
- transactions 41-60: normal-post phase, approximately 100 ms planned spacing.

The polling-burst detector threshold is fixed at 50 ms before execution. The first interval is treated as unavailable rather than as a measured zero interval.

### 4.3 Network impairment and capture point

Linux `tc netem` impairment is applied to the **client egress** path. Packet capture occurs in the **OpenPLC/server network namespace**. This distinction matters: the evidence measures what reaches the server-side observation point after the configured client-side impairment and TCP behavior.

Five conditions are evaluated:

| Condition | Delay | Jitter | Loss |
|---|---:|---:|---:|
| clean | 0 ms | 0 ms | 0% |
| delay20 | 20 ms | 0 ms | 0% |
| delay20_jitter5_loss5 | 20 ms | 5 ms | 5% |
| delay40_jitter10 | 40 ms | 10 ms | 0% |
| delay60_jitter10 | 60 ms | 10 ms | 0% |

### 4.4 Repeatability design

The v0.5 study executes five trials per condition, for 25 completed condition runs and 1,500 planned transactions. Condition order rotates between trials to reduce fixed-order drift effects. Ground truth remains based on the predeclared transaction schedule rather than detector output.

The report summarizes run-level metrics using arithmetic means, sample standard deviations, and exploratory two-sided 95% Student-t intervals. Because the metrics are bounded probabilities, displayed Student-t interval bounds are clipped to [0,1] for presentation, while the unbounded mathematical intervals are preserved in `aggregate.json` for transparency. With only five trials per condition, these intervals are descriptive repeatability indicators rather than population-level guarantees.

## 5. Results

### 5.1 Repeatability summary

| Condition | N | Coverage mean | Recall mean | Recall SD | Recall 95% t interval (display-clipped) | F1 mean | End-to-end recall mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 5 | 1.000 | 1.000 | 0.000 | 1.000-1.000 | 1.000 | 1.000 |
| delay20 | 5 | 1.000 | 1.000 | 0.000 | 1.000-1.000 | 1.000 | 1.000 |
| delay20_jitter5_loss5 | 5 | 1.000 | 0.950 | 0.087 | 0.842-1.000 | 0.973 | 0.950 |
| delay40_jitter10 | 5 | 1.000 | 0.420 | 0.057 | 0.349-0.491 | 0.590 | 0.420 |
| delay60_jitter10 | 5 | 1.000 | 0.000 | 0.000 | 0.000-0.000 | 0.000 | 0.000 |

Across the study, coverage remained 1.000, meaning all planned transactions remained represented at the server-side observation point. Detection performance nevertheless degraded as network delay and jitter altered inter-request timing.

### 5.2 Interpretation of the transition region

The detector's decision rule is intentionally simple: intervals below 50 ms are classified as a polling burst. Under clean conditions, the observed burst intervals remain well below that threshold. With +20 ms delay, they remain below the threshold and recall stays at 1.000. With +40 ms delay plus 10 ms jitter, observed burst timing straddles the 50 ms threshold, producing run-level recall between 0.35 and 0.50 and a mean of 0.420. With +60 ms delay plus 10 ms jitter, the observed burst intervals move above the threshold and recall falls to 0.000.

The +20 ms delay, 5 ms jitter, 5% loss condition is also informative. Coverage remains complete in the five reported runs, which is consistent with TCP preserving application-layer delivery at the capture point, but timing distortion still produces occasional false negatives. The run-level recall values are 1.00, 1.00, 1.00, 0.95, and 0.80.

### 5.3 What the result does and does not show

The result supports a specific claim: **for the documented isolated OpenPLC experiment and `polling-burst-v1` detector, network-path impairment can reduce timing-based detection recall even when application-layer observation coverage remains complete.**

The result does not establish that all OT detectors behave this way, that a 50 ms threshold is operationally optimal, or that these measurements predict performance in a production plant. Instead, it demonstrates why connectivity resilience should be measured explicitly rather than inferred from clean-network detector scores.

## 6. Reproducibility

The software release is tagged `v0.5.0-alpha` and points to commit `8f79f77f6a410d4c648ca7dbddd3e1b5a4148edb`. Release verification covers the complete pytest suite, source distribution build, wheel build, installed-wheel smoke test, Ubuntu Python 3.10/3.12, and Windows Python 3.10/3.12.

The GitHub release includes the Python wheel, source distribution, and `SHA256SUMS.txt`. Experimental evidence is stored in the repository with per-run integrity manifests. The repeatability study manifest records 25 completed condition runs and 1,500 planned transactions.

A clean software verification can be performed with:

```bash
git clone https://github.com/ASHTHRA/otshield-bench.git
cd otshield-bench
git checkout v0.5.0-alpha
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
./scripts/verify_release.sh
```

The isolated lab experiment requires Docker/Compose and should only be run in an authorized laboratory environment. The repository's repeatability runner is `scripts/run_resilience_replicates.sh`.

## 7. Threats to Validity and Limitations

The v0.5 evidence intentionally has a narrow scope.

**Laboratory realism.** The environment is a minimal isolated OpenPLC setup, not a full GRFICSv3 process simulation and not a production industrial network.

**Protocol scope.** Measured evidence is currently Modbus/TCP only. DNP3 and EtherNet/IP are project targets but are not experimentally validated in this release.

**Detector scope.** The principal repeated result concerns a simple timing-threshold detector. It should not be generalized to signature, statistical, machine-learning, or commercial OT detection products without separate measurement.

**Sample size.** Five runs per condition are sufficient for an exploratory repeatability milestone but not for strong population-level statistical inference. Additional runs are especially valuable in transition-region conditions where variance is observed.

**Network model.** The study uses configured `netem` delay, jitter, and loss at client egress. Other impairment models, queue behavior, asymmetric paths, packet reordering, bandwidth constraints, and physical-network effects remain future work.

**Capture point.** Server-side capture measures traffic that reaches the OpenPLC network namespace. A different observation point can produce different visibility and timing characteristics.

**External validation.** Independent reproduction, peer review, industry adoption, and production deployment have not yet been established.

## 8. Relevance to OT and Critical-Infrastructure Cybersecurity

NIST identifies OT security as requiring attention to performance, reliability, and safety constraints in systems that interact with physical processes [1]. CISA's cross-sector goals emphasize measurable cybersecurity outcomes for critical-infrastructure organizations, including detection-oriented practices [2]. Within that context, vendor-neutral and reproducible benchmarking can help distinguish nominal detector effectiveness from robustness under operationally degraded conditions.

OTShield's contribution is methodological rather than product-specific: preserve the ground truth, observation conditions, resource measurements, provenance, and connectivity impairments together so that a detection score can be interpreted in context. This approach can support more transparent evaluation of defensive monitoring methods used in manufacturing, energy, water, transportation, and other OT-heavy environments, while maintaining clear boundaries between laboratory evidence and production claims.

## 9. Future Work

The next research priorities are:

1. increase the number of runs in the transition-region conditions to strengthen variance estimates;
2. evaluate a detector whose threshold or model is trained independently on a separate normal dataset;
3. add experimental DNP3 support;
4. add experimental EtherNet/IP support;
5. move from the minimal OpenPLC lab to a documented full-GRFICS process simulation when environment prerequisites are satisfied;
6. obtain independent reproduction by a third party or separate laboratory;
7. publish software and report records with persistent identifiers and versioned citation metadata.

## 10. Conclusion

OTShield Bench v0.5.0-alpha demonstrates an evidence-preserving method for evaluating OT detection effectiveness and resilience under controlled network degradation. The repeated OpenPLC study shows that complete transaction visibility does not guarantee stable performance for a timing-sensitive detector: recall remained 1.000 in clean and +20 ms conditions, declined to 0.950 under moderate jitter/loss, fell to 0.420 around the threshold transition region, and reached 0.000 under +60 ms delay with jitter. The principal value of the benchmark is not the absolute score of one detector, but the reproducible framework that ties detector metrics to network condition, ground truth, resource measurements, and provenance.

## References

[1] K. Stouffer et al., *Guide to Operational Technology (OT) Security*, NIST Special Publication 800-82 Rev. 3, 2023. DOI: https://doi.org/10.6028/NIST.SP.800-82r3

[2] Cybersecurity and Infrastructure Security Agency, *Cross-Sector Cybersecurity Performance Goals*. https://www.cisa.gov/cybersecurity-performance-goals

[3] MITRE, *MITRE Engenuity Releases First ATT&CK Evaluations for Industrial Control Systems Security Tools*, July 19, 2021. https://www.mitre.org/news-insights/media-coverage/mitre-engenuity-releases-first-attck-evaluations-industrial-control

[4] D. Formby, *GRFICS: Graphical Realism Framework for Industrial Control Simulations*. https://github.com/djformby/GRFICS

[5] J. R. Palle, *OTShield Bench v0.5.0-alpha*, GitHub software release, September 20, 2026. https://github.com/ASHTHRA/otshield-bench/releases/tag/v0.5.0-alpha
