# OTB-DETECT/0.1

`predict(events)` returns exactly one detection per observed event, retaining its
`event_id`. Fields: `schema` = `OTB-DETECT/0.1`, nonempty `event_id`, boolean `alert`,
finite `score`, and nonempty `detector` version identifier. Higher scores indicate
greater anomaly evidence, but scores are not comparable across detector types.

`rules-v1` alerts when function != 3, address > 9, value outside [40,60], or source
interval < 50 ms. Its score is 0 or 1. Latency alone does not trigger this baseline.

`isolation-forest-v1` uses features in this order: function code, address, value,
source interval, latency. It uses 100 trees, contamination `auto`, one worker,
and a seeded random state. Score is negative `decision_function`; alert iff score > 0.
Fit requires at least 10 known-normal events. Predict before fit is rejected.
The CLI trains once on a separate normal stream of max(200,count) with seed + 1.
IDs, timestamps, scenario names, and labels never enter the feature matrix.

Labels are used only to validate the known-normal training contract and evaluate
predictions. Empty predictions are allowed after fitting. Future detectors must
document feature definitions, training provenance, thresholds, and score direction.
