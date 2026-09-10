from dataclasses import replace
import json
import math
import pytest
from otshield.cli import main
from otshield.core import SCENARIOS, faults, generate
from otshield.detectors import Detection, IsolationForestDetector, RuleDetector, features
from otshield.evaluation import evaluate


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenarios_and_rules(name):
    events = generate(name)
    assert events == generate(name)
    assert events != generate(name, seed=1)
    assert len({e.event_id for e in events}) == 200
    assert sum(e.label for e in events) == (0 if name == "normal" else 50)
    metrics = evaluate(events, events, RuleDetector().predict(events))
    assert metrics["fp"] == metrics["fn"] == 0
    assert metrics["coverage"] == 1


def test_faults_preserve_truth_and_are_reproducible():
    events = generate("value_spike")
    assert faults(events) == events
    assert faults(events, loss=1) == []
    observed = faults(events, .3, 10, 500)
    assert observed == faults(events, .3, 10, 500)
    assert 0 < len(observed) < len(events)
    assert observed == sorted(observed, key=lambda e: (e.timestamp_ms, e.event_id))
    lookup = {e.event_id: e for e in events}
    for event in observed:
        original = lookup[event.event_id]
        assert event.label == original.label
        assert event.interval_ms == original.interval_ms
        assert 10 <= event.latency_ms - original.latency_ms <= 510
        assert event.timestamp_ms - original.timestamp_ms == pytest.approx(event.latency_ms - original.latency_ms)


@pytest.mark.parametrize("kwargs", [{"loss": -1}, {"loss": 2}, {"latency_ms": -1},
                                   {"jitter_ms": -1}, {"loss": math.nan}, {"latency_ms": math.inf}])
def test_invalid_faults(kwargs):
    with pytest.raises(ValueError):
        faults([], **kwargs)


def test_known_confusion_matrix_and_loss():
    base = generate("normal")[:4]
    truth = [replace(e, label=i < 2) for i, e in enumerate(base)]
    detections = [Detection(e.event_id, i % 2 == 0, 0.0, "test") for i, e in enumerate(truth)]
    report = evaluate(truth, truth, detections)
    assert [report[k] for k in ("tp", "fp", "fn", "tn")] == [1, 1, 1, 1]
    assert report["precision"] == report["recall"] == report["f1"] == .5
    report = evaluate(truth, truth[:1], detections[:1])
    assert report["recall"] == 1 and report["end_to_end_recall"] == .5
    assert report["coverage"] == .25
    assert evaluate(truth, [], [])["end_to_end_recall"] == 0
    assert evaluate([], [], [])["f1"] == 0


def test_metrics_reject_bad_alignment():
    events = generate("normal")
    predictions = RuleDetector().predict(events)
    for truth, observed, detections in [(events * 2, events, predictions),
                                         (events, events * 2, predictions),
                                         (events, events, predictions * 2),
                                         (events, events, predictions[:-1]),
                                         ([], events, predictions)]:
        with pytest.raises(ValueError):
            evaluate(truth, observed, detections)


def test_isolation_forest_independent_training_and_no_label_leakage():
    train = generate("normal", seed=1)
    test = generate("value_spike", seed=2)
    model = IsolationForestDetector().fit(train)
    predictions = model.predict(test)
    assert predictions == IsolationForestDetector().fit(train).predict(test)
    assert predictions == model.predict([replace(e, label=not e.label) for e in test])
    assert all(math.isfinite(d.score) for d in predictions)
    assert any(d.alert for d in predictions)
    assert model.predict([]) == []
    assert features(test[0]) == features(replace(test[0], label=True))
    with pytest.raises(ValueError):
        IsolationForestDetector().predict(test)
    for bad in ([], train[:9], test):
        with pytest.raises(ValueError):
            model.fit(bad)


@pytest.mark.parametrize("detector", ["rules", "iforest"])
def test_cli(tmp_path, detector):
    output = tmp_path / "report.json"
    main(["--detector", detector, "--loss", "0.2", "--latency-ms", "5", "--output", str(output)])
    report = json.loads(output.read_text())
    assert len(report["results"]) == 5
    assert all(r["metrics"]["total"] == 200 for r in report["results"])
    previous = output.read_bytes()
    main(["--detector", detector, "--loss", "0.2", "--latency-ms", "5", "--output", str(output)])
    assert output.read_bytes() == previous


@pytest.mark.parametrize("args", [["--count", "0"], ["--loss", "nan"], ["--scenario", "unknown"]])
def test_cli_invalid(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("change", [{"address": -1}, {"value": math.nan}, {"label": 1},
                                    {"function_code": 0}, {"interval_ms": -1}, {"schema": "bad"}])
def test_telemetry_validation(change):
    with pytest.raises(ValueError):
        replace(generate("normal")[0], **change)


def test_generation_validation():
    for count in (0, 9, 10.5, True):
        with pytest.raises(ValueError):
            generate("normal", count)
    with pytest.raises(ValueError):
        generate("unknown")


@pytest.mark.parametrize("change", [{"event_id": 1}, {"score": True}, {"score": "1"},
                                    {"score": math.inf}, {"detector": 1}, {"alert": 1}])
def test_detection_validation(change):
    with pytest.raises(ValueError):
        replace(Detection("test:0", False, 0.0, "test"), **change)


def test_bundled_scenario_contracts():
    from importlib.resources import files
    for name in SCENARIOS:
        config = json.loads(files("otshield").joinpath("scenarios", name + ".json").read_text())
        assert config["schema"] == "OTB-SCENARIO/0.1"
        assert config["id"] == name and config["synthetic_only"] is True
        assert config["description"]
