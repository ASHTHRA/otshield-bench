"""Ground‑truth derivation utilities.

The experiment protocol is a JSON file describing a sequence of
*phases* (or *events*) that are expected to occur during a benchmark run.
Each event is a mapping with the following keys:

- ``start`` (float): start time in seconds, relative to the beginning of the experiment.
- ``end``   (float): end time in seconds, must be greater than ``start``.
- ``label`` (str):   human‑readable identifier for the event (e.g., ``"normal"``,
  ``"fault"``).
- ``provenance`` (str, optional): ``"synthetic"`` or ``"lab"`` indicating whether the
  event description is synthetic or derived from a lab measurement.  If omitted,
  ``"synthetic"`` is assumed.

The module provides:

- :class:`Event` – a lightweight immutable representation of a ground‑truth event.
- :func:`load_protocol` – load a JSON protocol file and return a list of raw dicts.
- :func:`derive_ground_truth` – validate the raw protocol and return a list of
  :class:`Event` objects sorted by start time.

Both functions raise :class:`ValueError` on malformed input or overlapping windows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable ground‑truth event."""
    start: float
    end: float
    label: str
    provenance: str = "synthetic"


def _validate_event_dict(d: dict) -> Event:
    """Validate a single event dictionary and convert it to :class:`Event`.

    Expected keys are ``start``, ``end``, ``label`` and optionally ``provenance``.
    ``start`` and ``end`` must be numbers with ``end > start``.
    ``label`` must be a non‑empty string.
    ``provenance`` if present must be either ``\"synthetic\"`` or ``\"lab\"``.
    """
    required = {"start", "end", "label"}
    missing = required - d.keys()
    if missing:
        raise ValueError(f"Event missing required keys: {sorted(missing)}")

    try:
        start = float(d["start"])
        end = float(d["end"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Event start/end must be numeric: {exc}") from exc

    if end <= start:
        raise ValueError(f"Event end ({end}) must be greater than start ({start})")

    label = str(d["label"])
    if not label:
        raise ValueError("Event label must be a non‑empty string")

    provenance = str(d.get("provenance", "synthetic")).lower()
    if provenance not in {"synthetic", "lab"}:
        raise ValueError("Provenance must be 'synthetic' or 'lab'")

    return Event(start=start, end=end, label=label, provenance=provenance)


def load_protocol(path: Path | str) -> List[dict]:
    """Load a JSON protocol file.

    The file must contain a JSON array where each element is an event dict.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read protocol file {p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in protocol file {p}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("Protocol JSON must be a list of event objects")
    return data


def derive_ground_truth(raw_events: Iterable[dict]) -> List[Event]:
    """Validate a protocol and return a deterministic list of :class:`Event`.

    The returned list is sorted by ``start`` time.  Overlapping windows are
    considered an error because ground‑truth must be unambiguous.
    """
    events = [_validate_event_dict(d) for d in raw_events]

    # Detect overlapping windows
    events_sorted = sorted(events, key=lambda e: e.start)
    for prev, cur in zip(events_sorted, events_sorted[1:]):
        if cur.start < prev.end:
            raise ValueError(
                f"Overlapping events detected: [{prev.start}, {prev.end}) "
                f"overlaps with [{cur.start}, {cur.end})"
            )
    return events_sorted
