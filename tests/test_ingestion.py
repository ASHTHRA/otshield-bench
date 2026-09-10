import json
from pathlib import Path

import pytest

from otshield.adapters import JsonTelemetryAdapter
from otshield.cli import main
from otshield.core import generate
from otshield.detectors import IsolationForestDetector, RuleDetector


FIXTURE = Path(__file__).parent / "fixtures" / "grfics_like_ingest.json"


def fixture_source():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_source(tmp_path, source):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path


def test_valid_grfics_like_ingestion_is_deterministic():
    adapter = JsonTelemetryAdapter()
    first = adapter.load(FIXTURE)
    second = adapter.load(FIXTURE)
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.schema == "OTB-INGEST/0.1"
    assert first.provenance.source == "grfics"
    assert first.provenance.evidence_type == "sanitized_fixture"
    assert [event.schema for event in first.events] == ["OTB-TELEMETRY/0.1"] * 2
    assert first.records[0].context.operation == "read_holding_registers"
    assert first.records[1].context.operation == "write_single_register"
    assert first.records[1].context.source_endpoint is None
    assert first.to_dict()["records"][1]["context"]["source_endpoint"] is None


def test_existing_detectors_accept_ingested_telemetry():
    dataset = JsonTelemetryAdapter().load(FIXTURE)
    rules = RuleDetector().predict(dataset.events)
    model = IsolationForestDetector().fit(generate("normal", seed=100))
    learned = model.predict(dataset.events)
    assert [d.event_id for d in rules] == ["fixture:0", "fixture:1"]
    assert rules[0].alert is False and rules[1].alert is True
    assert len(learned) == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda source: source.update(schema="bad"), "root.schema"),
        (lambda source: source["provenance"].pop("source"), "missing field"),
        (lambda source: source["provenance"].update(source="unknown"), "provenance source"),
        (lambda source: source["records"][0].pop("address"), "missing field"),
        (lambda source: source["records"][0].update(label="false"), "label must be boolean"),
        (lambda source: source["records"][0].update(operation=""), "operation must be"),
        (lambda source: source["records"][0].update(extra=True), "unknown field"),
        (lambda source: source.update(records=[]), "at least one record"),
        (lambda source: source["records"].append(source["records"][0]), "duplicate event IDs"),
    ],
)
def test_malformed_or_incomplete_input_is_rejected(tmp_path, change, message):
    source = fixture_source()
    change(source)
    with pytest.raises(ValueError, match=message):
        JsonTelemetryAdapter().load(write_source(tmp_path, source))


def test_malformed_json_and_nonfinite_number_are_rejected(tmp_path):
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read ingestion JSON"):
        JsonTelemetryAdapter().load(malformed)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text(FIXTURE.read_text(encoding="utf-8").replace("50.0", "NaN"), encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        JsonTelemetryAdapter().load(nonfinite)


def test_synthetic_telemetry_contract_is_unchanged():
    event = generate("normal", count=10)[0]
    assert event.schema == "OTB-TELEMETRY/0.1"
    assert set(event.to_dict()) == {
        "event_id", "timestamp_ms", "function_code", "address", "value",
        "interval_ms", "latency_ms", "label", "schema",
    }


def test_cli_ingest_writes_deterministic_normalized_json(tmp_path):
    output = tmp_path / "nested" / "normalized.json"
    main(["ingest", str(FIXTURE), "--output", str(output)])
    first = output.read_bytes()
    normalized = json.loads(first)
    assert normalized["schema"] == "OTB-INGEST/0.1"
    assert normalized["provenance"]["source"] == "grfics"
    assert normalized["records"][0]["telemetry"]["schema"] == "OTB-TELEMETRY/0.1"
    main(["ingest", str(FIXTURE), "--output", str(output)])
    assert output.read_bytes() == first


@pytest.mark.parametrize("input_name", ["missing.json", "malformed.json"])
def test_cli_ingest_reports_input_errors(tmp_path, input_name):
    input_path = tmp_path / input_name
    if input_name == "malformed.json":
        input_path.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["ingest", str(input_path), "--output", str(tmp_path / "output.json")])
    assert error.value.code == 2
    assert not (tmp_path / "output.json").exists()


def test_legacy_cli_invocation_remains_supported(tmp_path):
    output = tmp_path / "benchmark.json"
    main(["--scenario", "normal", "--count", "10", "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["version"] == "0.2.0a0"
    assert report["results"][0]["metrics"]["total"] == 10
