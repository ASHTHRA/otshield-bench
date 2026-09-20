"""Preregistered paired study accounting and run-level Student-t analysis."""
import hashlib
import json
import math
import statistics
import struct
from pathlib import Path

from scipy.stats import t

from .canonical_v06 import canonicalize_capture
from .core import Event
from .results import BenchmarkResultManifest, ResourceCostMetrics, DegradedConnectivity
from .lab_resilience import _hash, validate_protocol
from .paired_v06 import CALIBRATION_SHA256, DETECTORS, load_calibration

CONDITIONS = (
    ("clean", 0, 0, 0), ("delay20", 20, 0, 0),
    ("delay20_jitter5_loss5", 20, 5, 5),
    ("delay40_jitter10", 40, 10, 0), ("delay60_jitter10", 60, 10, 0),
)
TRIALS = 25
METRICS = ("recall", "f1", "coverage", "end_to_end_recall", "precision", "tp", "fp", "fn", "tn")
COSTS = ("wall_time_ms", "cpu_time_ms", "peak_memory_mb")
REQUIRED = ("raw.pcap", "protocol.json", "normalized.json", "provenance.json", "normalization.json") + tuple(
    f"{name}.{suffix}" for name in DETECTORS for suffix in ("result.json", "result.md", "observations.json"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, document):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def plan():
    return [{"trial": trial, "condition": CONDITIONS[(step + trial - 1) % 5][0],
             "planned_transactions": 60} for trial in range(1, TRIALS + 1) for step in range(5)]


def stats(values):
    values = list(values)
    if not values or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("finite nonempty measurements required")
    n, mean = len(values), statistics.mean(values)
    sd = statistics.stdev(values) if n > 1 else None
    margin = float(t.ppf(0.975, n - 1)) * sd / math.sqrt(n) if n > 1 else None
    return {"n": n, "mean": mean, "sd": sd, "min": min(values), "max": max(values),
            "ci95_unbounded_low": mean - margin if margin is not None else None,
            "ci95_unbounded_high": mean + margin if margin is not None else None}


def validate_pcap_container(path):
    """Check classic Ethernet PCAP framing without performing a second normalization."""
    raw = Path(path).read_bytes()
    endian = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
              b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">"}.get(raw[:4])
    if len(raw) < 24 or endian is None:
        raise ValueError("invalid PCAP header")
    major, minor, _, _, snaplen, network = struct.unpack(endian + "HHiIII", raw[4:24])
    if (major, minor, network) != (2, 4, 1) or snaplen <= 0:
        raise ValueError("invalid PCAP format")
    offset = 24
    while offset < len(raw):
        if len(raw) - offset < 16:
            raise ValueError("truncated PCAP packet header")
        _, _, captured, original = struct.unpack(endian + "IIII", raw[offset:offset + 16])
        offset += 16
        if captured > snaplen or captured > original or captured > len(raw) - offset:
            raise ValueError("invalid PCAP packet length")
        offset += captured


def validate_run(root, trial, condition):
    root = Path(root)
    for name in REQUIRED:
        if not (root / name).is_file() or (root / name).stat().st_size == 0:
            raise ValueError(f"missing or empty {name}")
    lines = (root / "SHA256SUMS").read_text().splitlines()
    hashes = {}
    for line in lines:
        checksum, name = line.split("  ", 1)
        if name in hashes:
            raise ValueError("duplicate integrity entry")
        hashes[name] = checksum
    if set(hashes) != set(REQUIRED) or any(digest(root / name) != hashes[name] for name in REQUIRED):
        raise ValueError("run integrity mismatch")
    validate_pcap_container(root / "raw.pcap")
    read = lambda name: json.loads((root / name).read_text())
    protocol, normalized = read("protocol.json"), read("normalized.json")
    requests = validate_protocol(protocol)
    spec = next(c for c in CONDITIONS if c[0] == condition)
    c = protocol["condition"]
    if (c["name"], c["delay_ms"], c["jitter_ms"], c["loss_percent"]) != spec or c["threshold_ms"] != 50:
        raise ValueError("condition differs from preregistration")
    if protocol.get("trial") != trial or c.get("impairment_direction") != "client-egress" or set(requests) != set(range(1, 61)):
        raise ValueError("invalid trial or transaction schedule")
    for tid, row in requests.items():
        burst = 21 <= tid <= 40
        expected = ("controlled-burst" if burst else "normal-pre" if tid <= 20 else "normal-post",
                    (tid - 1) % 10, None if tid == 1 else 10.0 if burst else 100.0, burst)
        if (row["phase"], row["address"], row["planned_interval_ms"], row["expected_anomaly"]) != expected:
            raise ValueError("ground truth differs from preregistration")
    provenance, normalization = read("provenance.json"), read("normalization.json")
    dataset_id = protocol["dataset_id"]
    if (normalized.get("schema") != "OTB-INGEST/0.1" or
            normalized["provenance"].get("evidence_type") != "lab_capture" or
            normalized["provenance"].get("dataset_id") != dataset_id or
            provenance.get("schema") != "OTB-LAB-EVIDENCE/0.1" or
            provenance.get("dataset_id") != dataset_id or
            provenance.get("capture_point") != "OpenPLC/server network namespace" or
            provenance.get("impairment_direction") != "client-egress" or
            not provenance.get("git_commit") or
            provenance.get("raw_pcap_sha256") != hashes["raw.pcap"] or
            normalization.get("schema") != "OTB-NORMALIZATION-EVIDENCE/0.1" or
            normalization.get("dataset_id") != dataset_id or
            normalization.get("input_sha256") != hashes["raw.pcap"] or
            normalization.get("output_sha256") != hashes["normalized.json"] or
            normalization.get("record_count") != len(normalized["records"])):
        raise ValueError("invalid provenance or normalization")
    canonical, audit = canonicalize_capture(normalized)
    observed = {}
    for record in canonical["records"]:
        metadata = record["context"]["value_metadata"]
        tid = metadata["transaction_id"]
        if type(tid) is not int or tid not in requests or tid in observed or metadata["status"] not in (
                "matched", "unmatched_request", "unmatched_response"):
            raise ValueError("invalid normalized transaction")
        observed[tid] = (metadata["status"], Event(**record["telemetry"]))
    results, observations = {}, []
    calibration = load_calibration(root.parents[1] / "calibration.json")
    for name, threshold in zip(DETECTORS, (50.0, calibration["calibration"]["threshold_ms"])):
        result, obs = read(f"{name}.result.json"), read(f"{name}.observations.json")
        BenchmarkResultManifest(**{**result,
            "resource_cost": ResourceCostMetrics(**result["resource_cost"]),
            "degraded_connectivity": DegradedConnectivity(**result["degraded_connectivity"])})
        env = result["environment"]
        # Older duplicate-free v0.6 artifacts remain valid; resolutions require audit.
        for metadata in (env, obs):
            if ("canonicalization" in metadata or audit["decisions"]) and metadata.get("canonicalization") != audit:
                raise ValueError("invalid canonicalization audit")
        if (result.get("schema") != "OTB-RESULT/0.1" or result.get("detector_adapter") != name or
                env.get("threshold_ms") != threshold or env.get("calibration_sha256") != CALIBRATION_SHA256 or
                env.get("experiment_protocol_sha256") != _hash(protocol) or
                env.get("normalized_capture_sha256") != _hash(normalized) or
                obs.get("normalized_capture_sha256") != _hash(normalized) or
                obs.get("detector") != name or len(obs["records"]) != 60 or
                result["effectiveness"]["total"] != 60):
            raise ValueError("invalid paired result")
        if obs.get("schema") != "OTB-LAB-RESILIENCE-OBSERVATIONS/0.1":
            raise ValueError("invalid observations schema")
        for tid, row in enumerate(obs["records"], 1):
            expected = requests[tid]
            status, event = observed.get(tid, ("not_observed", None))
            matched = status == "matched"
            if (row.get("transaction_id") != tid or
                    any(row.get(k) != expected[k] for k in ("phase", "expected_anomaly", "planned_interval_ms")) or
                    row.get("transport_status") != status or
                    row.get("observed_interval_ms") != (event.interval_ms if matched else None) or
                    row.get("observed_latency_ms") != (event.latency_ms if matched else None) or
                    (type(row.get("alert")) is not bool if matched else row.get("alert") is not None)):
                raise ValueError("observations do not match capture and protocol")
        for key in METRICS:
            stats([result["effectiveness"][key]])
        for key in COSTS:
            stats([result["resource_cost"][key]])
        observations.append([{k: v for k, v in row.items() if k != "alert"} for row in obs["records"]])
        results[name] = result
    if observations[0] != observations[1]:
        raise ValueError("detectors did not observe identical data")
    return results


def aggregate(runs):
    output = {}
    for condition, *_ in CONDITIONS:
        selected = [r for r in runs if r["condition"] == condition]
        if not selected:
            continue
        output[condition] = {
            "detectors": {name: {**{key: stats(r["results"][name]["effectiveness"][key] for r in selected) for key in METRICS},
                                  **{key: stats(r["results"][name]["resource_cost"][key] for r in selected) for key in COSTS}}
                          for name in DETECTORS},
            "paired_robust_minus_baseline": {key: stats(r["results"][DETECTORS[1]]["effectiveness"][key] -
                                                          r["results"][DETECTORS[0]]["effectiveness"][key] for r in selected)
                                            for key in ("recall", "f1")},
        }
    return {"schema": "OTB-V06-AGGREGATE/0.1", "conditions": output,
            "confidence_interval": "two-sided 95% Student-t; unbounded run-level intervals",
            "interpretation": "isolated OpenPLC laboratory only; no universal superiority claim"}


def finalize(root, execution_commit, failure=None):
    root = Path(root)
    completed, attempts, unattempted = [], [], []
    for item in plan():
        directory = root / f'trial-{item["trial"]}' / item["condition"]
        if not directory.exists():
            unattempted.append(item)
            continue
        try:
            results = validate_run(directory, item["trial"], item["condition"])
            completed.append({**item, "results": results})
            attempts.append({**item, "status": "completed"})
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            attempts.append({**item, "status": "failed", "reason": str(exc)})
    failed = [a for a in attempts if a["status"] == "failed"]
    manifest = {"schema": "OTB-V06-STUDY/0.1", "requested_trials_per_condition": 25,
                "condition_count": 5, "planned_condition_runs": 125,
                "planned_transactions_per_condition": 60, "planned_transactions_total": 7500,
                "planned_detector_evaluations": 250, "completed_condition_runs": len(completed),
                "completed_detector_evaluations": 2 * len(completed), "failed_attempts": failed,
                "attempts": attempts, "unattempted_runs": unattempted,
                "execution_git_commit": execution_commit, "calibration_sha256": CALIBRATION_SHA256,
                "infrastructure_failure": failure,
                "status": "completed" if len(completed) == 125 and not failure else "incomplete"}
    write_json(root / "aggregate.json", aggregate(completed))
    write_json(root / "study.json", manifest)
    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "STUDY_SHA256SUMS")
    (root / "STUDY_SHA256SUMS").write_text("".join(f"{digest(p)}  {p.relative_to(root)}\n" for p in paths))
    return manifest
