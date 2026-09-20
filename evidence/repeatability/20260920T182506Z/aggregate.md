# OTShield Resilience Repeatability Study

Five independent laboratory trials were requested per condition.

| Condition | N | Coverage mean | Recall mean | Recall SD | Recall 95% bounded CI | F1 mean | End-to-end recall mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 5 | 1.000 | 1.000 | 0.000 | 1.000–1.000 | 1.000 | 1.000 |
| delay20 | 5 | 1.000 | 1.000 | 0.000 | 1.000–1.000 | 1.000 | 1.000 |
| delay20_jitter5_loss5 | 5 | 1.000 | 0.950 | 0.087 | 0.842–1.000 | 0.973 | 0.950 |
| delay40_jitter10 | 5 | 1.000 | 0.420 | 0.057 | 0.349–0.491 | 0.590 | 0.420 |
| delay60_jitter10 | 5 | 1.000 | 0.000 | 0.000 | 0.000–0.000 | 0.000 | 0.000 |

## Interpretation boundary

This is an exploratory repeatability analysis with five runs per condition.

The 95% intervals are run-level Student-t intervals. Displayed probability bounds are limited to [0,1]; the raw unbounded mathematical bounds remain in aggregate.json for transparency.

The experiments use an isolated OpenPLC laboratory, read-only Modbus/TCP Function Code 3 traffic, the polling-burst-v1 detector, and client-egress netem impairment.
