# OTShield Degraded-Connectivity Resilience

| Condition | Loss | Delay ms | Jitter ms | Coverage | TP | FP | FN | TN | Precision | Recall | F1 | End-to-end recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 0.000 | 0.0 | 0.0 | 1.000 | 20 | 0 | 0 | 40 | 1.000 | 1.000 | 1.000 | 1.000 |
| delay20 | 0.000 | 20.0 | 0.0 | 1.000 | 20 | 0 | 0 | 40 | 1.000 | 1.000 | 1.000 | 1.000 |
| delay20_jitter5_loss5 | 0.050 | 20.0 | 5.0 | 1.000 | 19 | 0 | 1 | 40 | 1.000 | 0.950 | 0.974 | 0.950 |
| delay40_jitter10 | 0.000 | 40.0 | 10.0 | 1.000 | 10 | 0 | 10 | 40 | 1.000 | 0.500 | 0.667 | 0.500 |
| delay60_jitter10 | 0.000 | 60.0 | 10.0 | 1.000 | 0 | 0 | 20 | 40 | 0.000 | 0.000 | 0.000 | 0.000 |

These measurements apply only to this controlled isolated OpenPLC experiment.

TCP retransmission may preserve delivery under packet loss while increasing latency; therefore packet loss is not assumed to equal observation loss.
