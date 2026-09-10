# OTB-EVAL/0.1

Evaluation joins predictions to original ground truth by event ID. Duplicate IDs,
observations outside truth, and missing/extra predictions are rejected. Original
truth is authoritative even when observed telemetry contains a label field.

TP, FP, FN, TN count only observed events. Precision = TP/(TP+FP), recall =
TP/(TP+FN), F1 = 2TP/(2TP+FP+FN), false positive rate = FP/(FP+TN).
Zero denominators produce 0.0, including empty runs. These are event-level metrics.

`total`, `observed`, and `dropped` describe counts; `coverage` = observed/total.
`end_to_end_recall` = TP / all positive truth events, including dropped positives.
Dropped positives are not counted in observed FN. Always interpret observed recall
alongside coverage and end-to-end recall. No macro-averaged score is implied.

The enclosing CLI JSON includes package/runtime versions, detector, seed, count,
fault settings, and one entry per scenario containing truth, observations, detections,
and metrics. The metrics object's schema is `OTB-EVAL/0.1`.
This alpha does not measure runtime latency, event-episode detection delay, or
statistical confidence; injected network latency is not detector execution time.
