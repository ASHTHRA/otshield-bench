# Interpretation of the OpenPLC Degraded-Connectivity Experiment

## Scope

This experiment evaluates `polling-burst-v1` against a predeclared,
read-only Modbus/TCP polling-burst experiment in an isolated OpenPLC
laboratory.

Five network conditions were evaluated using client-egress `tc netem`
impairment while PCAP capture occurred in the OpenPLC/server network
namespace.

Each condition contained:

- 60 planned Modbus/TCP Function Code 3 transactions
- 40 normal transactions
- 20 controlled polling-burst anomalies
- 50 ms detector threshold

This is a single experimental run per condition.

## Observed results

| Condition | Coverage | TP | FP | FN | TN | Recall | F1 | End-to-end recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clean | 1.000 | 20 | 0 | 0 | 40 | 1.000 | 1.000 | 1.000 |
| delay20 | 1.000 | 20 | 0 | 0 | 40 | 1.000 | 1.000 | 1.000 |
| delay20_jitter5_loss5 | 1.000 | 19 | 0 | 1 | 40 | 0.950 | 0.974 | 0.950 |
| delay40_jitter10 | 1.000 | 10 | 0 | 10 | 40 | 0.500 | 0.667 | 0.500 |
| delay60_jitter10 | 1.000 | 0 | 0 | 20 | 40 | 0.000 | 0.000 | 0.000 |

## Timing mechanism

The detector identifies a polling burst when a measured inter-request
interval is below 50 ms.

Observed burst timing was:

| Condition | Mean burst interval | Minimum | Maximum | Intervals below 50 ms |
|---|---:|---:|---:|---:|
| clean | 10.995 ms | 10.851 ms | 11.270 ms | 20/20 |
| delay20 | 31.467 ms | 31.181 ms | 31.819 ms | 20/20 |
| delay20_jitter5_loss5 | 43.317 ms | 26.401 ms | 259.286 ms | 19/20 |
| delay40_jitter10 | 50.257 ms | 42.360 ms | 61.493 ms | 10/20 |
| delay60_jitter10 | 74.373 ms | 65.515 ms | 81.527 ms | 0/20 |

The experiment therefore separates two different properties:

1. **Observation availability**
   - all planned transactions remained represented in the normalized
     dataset for these runs;
   - observation coverage remained 1.0.

2. **Detection effectiveness**
   - network degradation changed the timing feature observed at the
     capture point;
   - this caused increasingly frequent false negatives even though
     transactions remained observable.

The 5% loss condition illustrates this distinction clearly. TCP behavior
preserved transaction visibility, but one burst interval expanded to
approximately 259.286 ms and was therefore missed by the timing detector.

## Result

For this controlled experiment, degradation of the network path reduced
the effectiveness of a timing-based OT detector without necessarily
reducing application-layer observation coverage.

The result demonstrates why benchmark reporting should distinguish:

- ingestion/observation coverage;
- detector recall;
- end-to-end recall;
- network impairment configuration.

## Evidence boundary

These measurements do not establish general OT detection performance.

They apply only to:

- this OpenPLC laboratory;
- Modbus/TCP Function Code 3 read traffic;
- the defined polling-burst scenario;
- the `polling-burst-v1` detector;
- one run per connectivity condition.

No claim is made regarding:

- production OT systems;
- all network conditions;
- all cyberattack classes;
- DNP3 or EtherNet/IP;
- full GRFICSv3 process simulation;
- statistical confidence across repeated experiments;
- independent external validation.

Repeated trials are required before estimating variance or confidence
intervals.
