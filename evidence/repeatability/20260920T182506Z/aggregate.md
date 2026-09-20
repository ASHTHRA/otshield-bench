# OTShield Resilience Repeatability Study

Five independent laboratory trials were requested per condition.

| Condition | N | Coverage mean | Recall mean | Recall SD | Recall 95% CI | F1 mean | End-to-end recall mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 5 | 1.000 | 1.000 | 0.000 | 1.000–1.000 | 1.000 | 1.000 |
| delay20 | 5 | 1.000 | 1.000 | 0.000 | 1.000–1.000 | 1.000 | 1.000 |
| delay20_jitter5_loss5 | 5 | 1.000 | 0.950 | 0.087 | 0.842–1.058 | 0.973 | 0.950 |
| delay40_jitter10 | 5 | 1.000 | 0.420 | 0.057 | 0.349–0.491 | 0.590 | 0.420 |
| delay60_jitter10 | 5 | 1.000 | 0.000 | 0.000 | 0.000–0.000 | 0.000 | 0.000 |

## Interpretation boundary

This is an exploratory repeatability analysis with five runs per condition.

The reported 95% intervals are run-level Student-t intervals and should not be interpreted as population-level production guarantees.

The experiments use an isolated OpenPLC laboratory, read-only Modbus/TCP Function Code 3 traffic, the polling-burst-v1 detector, and client-egress netem impairment.
