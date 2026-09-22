# Replication Result Template

## Researcher Information

- **Researcher:**
- **Organization:**

## Environment

- **Operating System:**
- **Kernel Version:**
- **Hardware Specifications:**

## Versions

- **Python Version:**
- **OTShield Bench Version:**
- **OpenPLC Version:**
- **Docker Version:**

## Commit

- **Execution Commit:**
- **Study Evidence Milestone:**
- **Documentation Milestone:**

## Run Counts

- **Trials:**
- **Conditions:**
- **Completed Condition Runs:**
- **Detector Evaluations:**
- **Planned Transactions:**
- **Failed Attempts:**
- **Unattempted Runs:**

## Per-Condition Metrics

### clean

| Metric | Baseline | Robust |
|--------|----------|--------|
| Recall | | |
| F1 | | |

### delay20

| Metric | Baseline | Robust |
|--------|----------|--------|
| Recall | | |
| F1 | | |

### delay20_jitter5_loss5

| Metric | Baseline | Robust |
|--------|----------|--------|
| Recall | | |
| F1 | | |

### delay40_jitter10

| Metric | Baseline | Robust |
|--------|----------|--------|
| Recall | | |
| F1 | | |

### delay60_jitter10

| Metric | Baseline | Robust |
|--------|----------|--------|
| Recall | | |
| F1 | | |

## Paired Effects

Document any paired differences between baseline and robust configurations
for each condition, including direction and magnitude.

## Integrity Verification

- **SHA-256 Checksums Verified:** [ ] Yes / [ ] No
- **Evidence Modified:** [ ] Yes / [ ] No
- **Checksum Match:** [ ] Yes / [ ] No

## Deviations

List any deviations from the reference results, including:

- Condition
- Metric
- Reference Value
- Observed Value
- Deviation Magnitude
- Possible Explanation

## Observations

Document any notable observations during replication, including environmental
differences, unexpected behavior, or configuration issues.

## Conclusion

This conclusion is limited to the lab environment and does not extend to
production systems, external networks, DNP3, EtherNet/IP, or any other
protocols or environments not tested in this study. No universal
detector-superiority claim is made.
