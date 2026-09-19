import json
from pathlib import Path

import pytest

from otshield.ground_truth import Event, derive_ground_truth, load_protocol


def test_load_and_derive_valid_protocol(tmp_path: Path):
    # Create a minimal valid protocol JSON file
    protocol = [
        {"start": 0, "end": 10, "label": "normal"},
        {"start": 10, "end": 20, "label": "fault", "provenance": "lab"},
    ]
    file_path = tmp_path / "protocol.json"
    file_path.write_text(json.dumps(protocol), encoding="utf-8")

    raw = load_protocol(file_path)
    events = derive_ground_truth(raw)

    assert events == [
        Event(start=0.0, end=10.0, label="normal", provenance="synthetic"),
        Event(start=10.0, end=20.0, label="fault", provenance="lab"),
    ]


def test_load_malformed_json(tmp_path: Path):
    file_path = tmp_path / "bad.json"
    file_path.write_text("{ not a valid json }", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_protocol(file_path)


def test_missing_required_keys():
    raw = [{"start": 0, "end": 5}]  # missing label
    with pytest.raises(ValueError, match="missing required keys"):
        derive_ground_truth(raw)


def test_overlapping_events():
    raw = [
        {"start": 0, "end": 10, "label": "a"},
        {"start": 5, "end": 15, "label": "b"},
    ]
    with pytest.raises(ValueError, match="Overlapping events"):
        derive_ground_truth(raw)


def test_non_numeric_times():
    raw = [{"start": "zero", "end": 10, "label": "a"}]
    with pytest.raises(ValueError, match="must be numeric"):
        derive_ground_truth(raw)
