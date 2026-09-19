# Ground‑Truth Protocol Schema

OTShield benchmarks rely on a **deterministic ground‑truth** that describes the
expected state of the system over time.  The ground‑truth is derived from an
*experiment protocol* – a small JSON document that enumerates the phases or
events that will occur during a run.

## JSON format

The file must contain a top‑level JSON array.  Each element describes a single
event with the following keys:

| Key          | Type   | Required | Description |
|--------------|--------|----------|-------------|
| `start`      | number | yes      | Start time in seconds, relative to the beginning of the experiment. |
| `end`        | number | yes      | End time in seconds; must be greater than `start`. |
| `label`      | string | yes      | Human‑readable identifier for the event (e.g., `"normal"` or `"fault"`). |
| `provenance`| string | no       | `"synthetic"` (default) or `"lab"` – indicates whether the event description is synthetic or derived from a lab measurement. |

### Example

```json
[
  { "start": 0, "end": 30, "label": "normal" },
  { "start": 30, "end": 45, "label": "fault", "provenance": "lab" }
]
```

## Validation rules

* All required keys must be present.
* `start` and `end` must be numeric, and `end` > `start`.
* `label` must be a non‑empty string.
* `provenance`, if supplied, must be `"synthetic"` or `"lab"`.
* Event windows must **not overlap**; overlapping windows make the ground‑truth ambiguous
  and cause a `ValueError`.

## API

```python
from otshield.ground_truth import load_protocol, derive_ground_truth

raw = load_protocol("protocol.json")
events = derive_ground_truth(raw)   # → List[Event]
```

`Event` objects are immutable dataclasses with fields `start`, `end`,
`label`, and `provenance`.  The returned list is sorted by `start` time,
ensuring deterministic output.

## Testing

The test suite (`tests/test_ground_truth.py`) covers:

* Successful parsing of a valid protocol.
* Detection of malformed JSON.
* Missing required keys.
* Overlapping windows.
* Non‑numeric time values.

Running the tests:

```bash
pytest -q
```

These utilities enable reproducible benchmark runs without any live
hardware, Docker containers, or external services.
