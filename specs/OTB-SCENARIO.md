# OTB-SCENARIO/0.1

Status: alpha. Canonical bundled definitions are `src/otshield/scenarios/*.json`.
Required fields: `schema` = `OTB-SCENARIO/0.1`, unique `id` from the five bundled
IDs, human-readable `description`, and `synthetic_only` = true.
Optional anomaly overrides: integer `function_code` (1–127), integer `address`
(0–65535), finite numeric `value`, and nonnegative finite `interval_ms`.
Custom scenario loading is not supported in this alpha.

The generator accepts a scenario ID, integer count >= 10, and RNG seed. Normal
events use function 3, uniformly sampled integer addresses 0–9, values in [45,55],
poll intervals in [95,105] ms, and latency in [1,3] ms. Source timestamps accumulate
polling intervals from zero. For non-normal scenarios, indices in
`[count // 2, 3 * count // 4)` receive anomaly overrides and positive labels.
All other events have negative labels. Event IDs are `scenario:seed:index`.

`register_scan` is a simplified out-of-policy probe, not a complete network scan.
No scenario opens sockets, encodes protocol messages, or targets external systems.
Reproducibility assumes the same package and runtime versions; do not combine
separate runs with identical IDs without an enclosing run identifier.
