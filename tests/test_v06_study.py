"""Synthetic runner tests: these are not OpenPLC experimental evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from otshield.paired_v06 import DETECTORS, write_paired_capture
from otshield.study_v06 import (CONDITIONS, REQUIRED, aggregate, digest, finalize,
                                plan, stats, validate_run, write_json)
from test_lab_resilience import _record

CALIBRATION = Path("research/v0.6_calibration.json")
linux_lab_only = pytest.mark.skipif(
    sys.platform != "linux",
    reason="OTShield v0.6 lab lifecycle/locking tests require POSIX/Linux semantics",
)


def make_run(study, trial=1, condition=CONDITIONS[0]):
    name, delay, jitter, loss = condition
    root = study / f"trial-{trial}" / name
    root.mkdir(parents=True)
    shutil.copyfile(CALIBRATION, study / "calibration.json")
    dataset_id = f"synthetic-test-{trial}-{name}"
    protocol = {"schema": "OTB-LAB-RESILIENCE-PROTOCOL/0.1", "dataset_id": dataset_id,
                "trial": trial, "condition": {"name": name, "delay_ms": delay,
                "jitter_ms": jitter, "loss_percent": loss, "threshold_ms": 50,
                "impairment_direction": "client-egress"}, "requests": []}
    for tid in range(1, 61):
        burst = 21 <= tid <= 40
        protocol["requests"].append({"transaction_id": tid, "address": (tid - 1) % 10,
            "expected_anomaly": burst, "planned_interval_ms": None if tid == 1 else 10 if burst else 100,
            "phase": "controlled-burst" if burst else "normal-pre" if tid <= 20 else "normal-post"})
    records = [_record(tid, 0 if tid == 1 else 70 if 21 <= tid <= 40 else 110) for tid in range(1, 61)]
    normalized = {"schema": "OTB-INGEST/0.1", "provenance": {
        "source": "synthetic-test", "dataset_id": dataset_id, "evidence_type": "lab_capture"}, "records": records}
    # Minimal synthetic PCAP container; no live network traffic is generated.
    import struct
    (root / "raw.pcap").write_bytes(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
    write_json(root / "protocol.json", protocol)
    write_json(root / "normalized.json", normalized)
    write_json(root / "provenance.json", {"schema": "OTB-LAB-EVIDENCE/0.1", "dataset_id": dataset_id,
        "capture_point": "OpenPLC/server network namespace", "impairment_direction": "client-egress",
        "git_commit": "synthetic-test", "raw_pcap_sha256": digest(root / "raw.pcap")})
    write_json(root / "normalization.json", {"schema": "OTB-NORMALIZATION-EVIDENCE/0.1",
        "dataset_id": dataset_id, "input_sha256": digest(root / "raw.pcap"),
        "output_sha256": digest(root / "normalized.json"), "record_count": 60})
    write_paired_capture(root / "normalized.json", root / "protocol.json", CALIBRATION, root)
    seal(root)
    return root


def seal(root):
    (root / "SHA256SUMS").write_text("".join(f"{digest(root / name)}  {name}\n" for name in REQUIRED))


def test_fixed_rotating_plan():
    schedule = plan()
    assert len(schedule) == 125
    assert sum(x["planned_transactions"] for x in schedule) == 7500
    assert len(schedule) * len(DETECTORS) == 250
    for trial in range(1, 26):
        rows = [r["condition"] for r in schedule if r["trial"] == trial]
        assert rows == [CONDITIONS[(step + trial - 1) % 5][0] for step in range(5)]


def test_student_t_unbounded():
    result = stats([0, 1])
    assert result["n"] == 2
    assert result["sd"] == pytest.approx(2 ** -0.5)
    assert result["ci95_unbounded_low"] == pytest.approx(0.5 - 12.706204736 * 0.5)
    assert result["ci95_unbounded_high"] > 1
    assert stats([1])["sd"] is None
    assert stats([1])["ci95_unbounded_low"] is None
    for values in ([], [float("nan")], [True]):
        with pytest.raises(ValueError):
            stats(values)


def test_paired_differences_are_run_level_and_signed():
    runs = []
    for a, b in [(1, 0), (0.8, 0.2)]:
        results = {name: {"effectiveness": {k: value for k in
                    ("recall", "f1", "coverage", "end_to_end_recall", "precision", "tp", "fp", "fn", "tn")},
                    "resource_cost": {k: 1 for k in ("wall_time_ms", "cpu_time_ms", "peak_memory_mb")}}
                   for name, value in zip(DETECTORS, (a, b))}
        runs.append({"condition": "clean", "results": results})
    result = aggregate(runs)["conditions"]["clean"]["paired_robust_minus_baseline"]["recall"]
    assert result["n"] == 2
    assert result["mean"] == pytest.approx(-0.8)
    assert result["sd"] == pytest.approx(0.4 / 2 ** 0.5)
    assert result["ci95_unbounded_low"] < -1


def test_full_success_accounting(tmp_path):
    for item in plan():
        spec = next(c for c in CONDITIONS if c[0] == item["condition"])
        make_run(tmp_path, item["trial"], spec)
    manifest = finalize(tmp_path, "synthetic-test")
    assert manifest["status"] == "completed"
    assert manifest["completed_condition_runs"] == 125
    assert manifest["completed_detector_evaluations"] == 250
    assert manifest["planned_transactions_total"] == 7500
    assert manifest["failed_attempts"] == manifest["unattempted_runs"] == []
    data = json.loads((tmp_path / "aggregate.json").read_text())
    for condition in data["conditions"].values():
        assert condition["paired_robust_minus_baseline"]["f1"]["n"] == 25
        for name in DETECTORS:
            assert condition["detectors"][name]["recall"]["n"] == 25
    for line in (tmp_path / "STUDY_SHA256SUMS").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        assert digest(tmp_path / name) == checksum


def test_failure_accounting_retains_attempts(tmp_path):
    make_run(tmp_path)
    failed = tmp_path / "trial-1/delay20"
    failed.mkdir()
    (failed / "protocol.json").write_text("{}")
    manifest = finalize(tmp_path, "synthetic-test", "capture failed")
    assert manifest["status"] == "incomplete"
    assert manifest["completed_condition_runs"] == 1
    assert len(manifest["failed_attempts"]) == 1
    assert len(manifest["unattempted_runs"]) == 123
    assert manifest["infrastructure_failure"] == "capture failed"


@pytest.mark.parametrize("name", REQUIRED + ("SHA256SUMS",))
def test_missing_evidence_fails_closed(tmp_path, name):
    root = make_run(tmp_path)
    (root / name).unlink()
    manifest = finalize(tmp_path, "synthetic-test")
    assert manifest["completed_condition_runs"] == 0
    assert len(manifest["failed_attempts"]) == 1


@pytest.mark.parametrize("name", ["protocol.json", "normalization.json", "provenance.json",
                                   "polling-burst-v1.result.json", "robust-polling-burst-v1.observations.json"])
def test_malformed_evidence_even_with_updated_hash_fails(tmp_path, name):
    root = make_run(tmp_path)
    write_json(root / name, {})
    seal(root)
    assert finalize(tmp_path, "synthetic-test")["completed_condition_runs"] == 0


def test_tampered_evidence_fails(tmp_path):
    root = make_run(tmp_path)
    (root / "raw.pcap").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        validate_run(root, 1, "clean")


@linux_lab_only
def test_dry_run_never_calls_docker_or_creates_output(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("v06_runner", "scripts/run_v06_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def forbidden(*args, **kwargs):
        pytest.fail("preflight must not launch subprocesses")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    output = tmp_path / "must-not-exist"
    for flag in ([], ["--dry-run"], ["--preflight"]):
        monkeypatch.setattr(sys, "argv", ["run_v06_study.py", *flag, "--output", str(output)])
        assert module.main() == 0
        assert not output.exists()
    assert "125 condition runs, 7500 planned transactions, 250" in capsys.readouterr().out


@linux_lab_only
def test_worker_has_one_capture_normalization_and_paired_evaluation():
    source = Path("scripts/run_v06_lab_worker.sh").read_text()
    assert source.count('        normalize_capture \\\n') == 1
    assert source.count('exec tcpdump') == 1
    assert source.count('scripts/evaluate_v06_paired.py') == 1
    assert 'TRIALS=25' in source
    assert 'git push' not in source and 'git commit' not in source
    subprocess.run(["bash", "-n", "scripts/run_v06_lab_worker.sh"], check=True)


def test_changed_observation_with_fresh_hash_fails(tmp_path):
    root = make_run(tmp_path)
    for detector in DETECTORS:
        path = root / f"{detector}.observations.json"
        data = json.loads(path.read_text())
        data["records"][1]["observed_interval_ms"] = 4
        write_json(path, data)
    seal(root)
    assert finalize(tmp_path, "synthetic-test")["completed_condition_runs"] == 0


def test_malformed_pcap_with_updated_hash_fails(tmp_path):
    root = make_run(tmp_path)
    (root / "raw.pcap").write_bytes(b"not a pcap")
    seal(root)
    assert finalize(tmp_path, "synthetic-test")["completed_condition_runs"] == 0


@linux_lab_only
def test_worker_failure_finalizes_manifest(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("v06_runner_failure", "scripts/run_v06_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "lab.lock")
    root = tmp_path / "new-study"
    monkeypatch.setattr(sys, "argv", ["run_v06_study.py", "--execute-lab", "--output", str(root)])
    monkeypatch.setattr(module.shutil, "which", lambda _: "/fake/docker")
    monkeypatch.setattr(module.subprocess, "check_output", lambda args, **kwargs:
                        "synthetic-commit" if args[1] == "rev-parse" else "")
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    class FakeWorker:
        args = ["synthetic-worker"]
        def __init__(self, *args, **kwargs):
            assert kwargs["env"]["V06_ROOT"] == str(root)
            (root / "trial-1/clean").mkdir(parents=True)
        def wait(self):
            return 1
    monkeypatch.setattr(module.subprocess, "Popen", FakeWorker)
    assert module.main() == 1
    manifest = json.loads((root / "study.json").read_text())
    assert len(manifest["failed_attempts"]) == 1
    assert "CalledProcessError" in manifest["infrastructure_failure"]
    assert (root / "STUDY_SHA256SUMS").exists()
