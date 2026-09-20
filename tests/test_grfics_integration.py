"""Tests for GRFICSv3/OpenPLC integration and capture pipeline.

These tests verify:
1. The capture script's traffic generation logic (no Docker needed)
2. The OTB-INGEST-SOURCE output format correctness
3. End-to-end pipeline with a local Modbus server
4. Existing ingestion contracts remain intact
5. Docker Compose configuration validity

Live GRFICS/OpenPLC capture tests are skipped if Docker is unavailable
or the OpenPLC container cannot start.
"""

import hashlib
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the capture module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from capture_grfics import (
    build_ingest_source,
    compute_provenance_meta,
    execute_polling,
    generate_polling_pattern,
    pcap_to_records,
)

from otshield.adapters import JsonTelemetryAdapter
from otshield.core import generate


FIXTURE = Path(__file__).parent / "fixtures" / "grfics_like_ingest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _docker_available() -> bool:
    """Check if Docker is available and the daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _openplc_running() -> bool:
    """Check if OpenPLC is already running on port 502."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 502))
        sock.close()
        return result == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Traffic generation tests (no Docker needed)
# ---------------------------------------------------------------------------

class TestTrafficGeneration:
    """Test the deterministic traffic generation logic."""

    def test_generate_polling_pattern_deterministic(self):
        """Same seed produces same operations."""
        ops1 = generate_polling_pattern(duration_s=1.0, seed=42)
        ops2 = generate_polling_pattern(duration_s=1.0, seed=42)
        assert ops1 == ops2
        assert len(ops1) > 0

    def test_generate_polling_pattern_different_seeds(self):
        """Different seeds produce different operations."""
        ops1 = generate_polling_pattern(duration_s=1.0, seed=42)
        ops2 = generate_polling_pattern(duration_s=1.0, seed=43)
        assert ops1 != ops2

    def test_generate_polling_pattern_duration(self):
        """Duration controls the number of operations."""
        ops_short = generate_polling_pattern(duration_s=0.5, poll_interval_s=0.1)
        ops_long = generate_polling_pattern(duration_s=2.0, poll_interval_s=0.1)
        assert len(ops_long) > len(ops_short)

    def test_generate_polling_pattern_has_anomalies(self):
        """Pattern includes labeled anomalies."""
        ops = generate_polling_pattern(duration_s=5.0, poll_interval_s=0.1, seed=42)
        labels = [op["label"] for op in ops]
        assert True in labels  # has anomalous operations
        assert False in labels  # has normal operations

    def test_generate_polling_pattern_valid_function_codes(self):
        """All operations use valid Modbus function codes."""
        from capture_grfics import FC_READ_HOLDING_REGISTERS, FC_WRITE_SINGLE_REGISTER
        ops = generate_polling_pattern(duration_s=2.0, seed=42)
        valid_fcs = {FC_READ_HOLDING_REGISTERS, FC_WRITE_SINGLE_REGISTER}
        for op in ops:
            assert op["function_code"] in valid_fcs

    def test_generate_polling_pattern_addresses_in_range(self):
        """Normal addresses are in valid register range."""
        ops = generate_polling_pattern(duration_s=2.0, seed=42)
        for op in ops:
            assert isinstance(op["address"], int)
            assert 0 <= op["address"] <= 65535


# ---------------------------------------------------------------------------
# Ingest source format tests
# ---------------------------------------------------------------------------

class TestIngestSourceFormat:
    """Test the OTB-INGEST-SOURCE/0.1 output format."""

    def _make_record(self, idx: int = 0) -> dict:
        return {
            "id": f"test:{idx}",
            "timestamp_ms": 100.0 + idx * 100.0,
            "function_code": 3,
            "address": idx % 10,
            "value": 50.0,
            "interval_ms": 100.0,
            "latency_ms": 2.0,
            "label": False,
        }

    def test_build_ingest_source_schema(self):
        """Output document has correct schema."""
        doc, _ = build_ingest_source(
            records=[self._make_record(0)],
            dataset_id="test-dataset",
        )
        assert doc["schema"] == "OTB-INGEST-SOURCE/0.1"

    def test_build_ingest_source_provenance(self):
        """Provenance fields are present."""
        doc, _ = build_ingest_source(
            records=[self._make_record(0)],
            dataset_id="test-dataset",
            evidence_type="lab_capture",
            source="grfics",
        )
        assert doc["provenance"]["source"] == "grfics"
        assert doc["provenance"]["dataset_id"] == "test-dataset"
        assert doc["provenance"]["evidence_type"] == "lab_capture"

    def test_build_ingest_source_provenance_meta(self):
        """Provenance metadata is returned separately."""
        meta = {"tool": "test", "version": "1.0"}
        doc, returned_meta = build_ingest_source(
            records=[self._make_record(0)],
            dataset_id="test-dataset",
            provenance_meta=meta,
        )
        assert returned_meta is not None
        assert returned_meta["tool"] == "test"
        # metadata is NOT in the main document (preserves strict schema)
        assert "_capture_metadata" not in doc

    def test_build_ingest_source_records(self):
        """Records are included in output."""
        records = [self._make_record(i) for i in range(5)]
        doc, _ = build_ingest_source(records=records, dataset_id="test-dataset")
        assert len(doc["records"]) == 5
        assert doc["records"][0]["id"] == "test:0"

    def test_build_ingest_source_is_json_serializable(self):
        """Output is valid JSON."""
        records = [self._make_record(i) for i in range(3)]
        doc, _ = build_ingest_source(records=records, dataset_id="test-dataset")
        content = json.dumps(doc, indent=2, sort_keys=True)
        parsed = json.loads(content)
        assert parsed["schema"] == "OTB-INGEST-SOURCE/0.1"

    def test_output_has_no_nan(self):
        """Output contains no NaN or Infinity values."""
        records = [self._make_record(0)]
        doc, _ = build_ingest_source(records=records, dataset_id="test-dataset")
        content = json.dumps(doc, allow_nan=False)
        assert "NaN" not in content
        assert "Infinity" not in content

    def test_compute_provenance_meta(self):
        """Provenance metadata includes expected fields."""
        meta = compute_provenance_meta(
            host="127.0.0.1", port=502, duration_s=10.0,
            poll_interval_s=0.1, seed=42,
        )
        assert meta["capture_tool"] == "otshield-bench/scripts/capture_grfics.py"
        assert meta["openplc_host"] == "127.0.0.1"
        assert meta["openplc_port"] == 502
        assert meta["capture_duration_s"] == 10.0
        assert meta["seed"] == 42
        assert "python_version" in meta
        assert "platform" in meta
        assert "timestamp_utc" in meta


# ---------------------------------------------------------------------------
# OTB-INGEST adapter round-trip tests
# ---------------------------------------------------------------------------

class TestIngestRoundTrip:
    """Test that generated OTB-INGEST-SOURCE passes through the adapter."""

    def _make_source_doc(self, records_count: int = 2) -> dict:
        """Create a valid OTB-INGEST-SOURCE document."""
        records = []
        for i in range(records_count):
            records.append({
                "id": f"roundtrip:{i}",
                "timestamp_ms": 100.0 + i * 100.0,
                "function_code": 3,
                "address": i,
                "value": 50.0 + i * 10.0,
                "interval_ms": 100.0,
                "latency_ms": 2.0 + i * 0.5,
                "label": i == records_count - 1,
            })
        return {
            "schema": "OTB-INGEST-SOURCE/0.1",
            "provenance": {
                "source": "grfics",
                "dataset_id": "roundtrip-test",
                "evidence_type": "lab_capture",
            },
            "records": records,
        }

    def test_roundtrip_through_adapter(self, tmp_path):
        """Generated source document passes through JsonTelemetryAdapter."""
        source = self._make_source_doc()
        path = tmp_path / "source.json"
        path.write_text(json.dumps(source), encoding="utf-8")

        adapter = JsonTelemetryAdapter()
        dataset = adapter.load(path)

        assert dataset.schema == "OTB-INGEST/0.1"
        assert dataset.provenance.source == "grfics"
        assert dataset.provenance.evidence_type == "lab_capture"
        assert len(dataset.records) == 2
        assert dataset.events[0].function_code == 3
        assert dataset.events[0].address == 0
        assert dataset.events[1].label is True

    def test_roundtrip_events_match_source(self, tmp_path):
        """Events in the dataset match the source records."""
        source = self._make_source_doc()
        path = tmp_path / "source.json"
        path.write_text(json.dumps(source), encoding="utf-8")

        dataset = JsonTelemetryAdapter().load(path)
        for i, record in enumerate(dataset.records):
            assert record.telemetry.event_id == f"roundtrip:{i}"
            assert record.telemetry.function_code == source["records"][i]["function_code"]
            assert record.telemetry.address == source["records"][i]["address"]
            assert record.telemetry.value == source["records"][i]["value"]

    def test_roundtrip_deterministic(self, tmp_path):
        """Same source document produces identical normalized output."""
        source = self._make_source_doc()
        path = tmp_path / "source.json"
        path.write_text(json.dumps(source), encoding="utf-8")

        adapter = JsonTelemetryAdapter()
        first = adapter.load(path)
        second = adapter.load(path)
        assert first.to_dict() == second.to_dict()


# ---------------------------------------------------------------------------
# End-to-end pipeline with real Modbus server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def modbus_server():
    """Start an OpenPLC container for testing."""
    if not _docker_available():
        pytest.skip("Docker not available")

    docker_dir = Path(__file__).parent.parent / "docker"
    compose_file = docker_dir / "docker-compose.grfics.yml"

    if not compose_file.exists():
        pytest.skip("Docker Compose file not found")

    # Start OpenPLC
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "openplc"],
            cwd=str(docker_dir),
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("Could not start Docker containers")

    # Wait for health
    timeout = 120
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Health.Status}}", "otshield-openplc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "healthy" in result.stdout:
                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        time.sleep(5)
    else:
        # Cleanup and skip
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            cwd=str(docker_dir),
            capture_output=True,
            timeout=30,
        )
        pytest.skip("OpenPLC did not become healthy")

    yield "127.0.0.1", 502

    # Cleanup
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "down", "-v"],
        cwd=str(docker_dir),
        capture_output=True,
        timeout=30,
    )


class TestEndToEndPipeline:
    """End-to-end tests that require a running Modbus server.

    These tests are skipped if:
    - Docker is not available
    - The OpenPLC container cannot start
    - Port 502 is not accessible
    """

    @pytest.mark.skipif(not _docker_available(), reason="Docker not available")
    def test_capture_produces_valid_source(self, tmp_path, modbus_server):
        """Live capture produces valid OTB-INGEST-SOURCE JSON."""
        host, port = modbus_server
        output = tmp_path / "capture.json"

        from capture_grfics import main
        main([
            "--host", host,
            "--port", str(port),
            "--output", str(output),
            "--duration", "2",
            "--poll-interval", "0.2",
            "--seed", "42",
        ])

        assert output.exists()
        doc = json.loads(output.read_text(encoding="utf-8"))
        assert doc["schema"] == "OTB-INGEST-SOURCE/0.1"
        assert len(doc["records"]) > 0
        assert doc["provenance"]["source"] == "grfics"
        assert doc["provenance"]["evidence_type"] == "lab_capture"
        # No NaN in output
        content = output.read_text(encoding="utf-8")
        assert "NaN" not in content

    @pytest.mark.skipif(not _docker_available(), reason="Docker not available")
    def test_capture_passes_through_adapter(self, tmp_path, modbus_server):
        """Live capture output passes through JsonTelemetryAdapter."""
        host, port = modbus_server
        capture_output = tmp_path / "capture.json"
        normalized_output = tmp_path / "normalized.json"

        from capture_grfics import main
        main([
            "--host", host,
            "--port", str(port),
            "--output", str(capture_output),
            "--duration", "2",
            "--poll-interval", "0.2",
            "--seed", "42",
        ])

        adapter = JsonTelemetryAdapter()
        dataset = adapter.load(capture_output)
        assert dataset.schema == "OTB-INGEST/0.1"
        assert len(dataset.records) > 0

    @pytest.mark.skipif(not _docker_available(), reason="Docker not available")
    def test_capture_is_deterministic(self, tmp_path, modbus_server):
        """Same seed produces same capture records."""
        host, port = modbus_server
        output1 = tmp_path / "capture1.json"
        output2 = tmp_path / "capture2.json"

        from capture_grfics import main
        main([
            "--host", host,
            "--port", str(port),
            "--output", str(output1),
            "--duration", "1",
            "--poll-interval", "0.5",
            "--seed", "99",
        ])
        main([
            "--host", host,
            "--port", str(port),
            "--output", str(output2),
            "--duration", "1",
            "--poll-interval", "0.5",
            "--seed", "99",
        ])

        doc1 = json.loads(output1.read_text())
        doc2 = json.loads(output2.read_text())
        # Records should be identical (same operations, same responses)
        assert len(doc1["records"]) == len(doc2["records"])
        for r1, r2 in zip(doc1["records"], doc2["records"]):
            assert r1["function_code"] == r2["function_code"]
            assert r1["address"] == r2["address"]
            assert r1["label"] == r2["label"]


# ---------------------------------------------------------------------------
# Docker Compose configuration tests
# ---------------------------------------------------------------------------

class TestDockerComposeConfig:
    """Validate the Docker Compose configuration."""

    def test_compose_file_exists(self):
        """The compose file exists."""
        compose_path = Path(__file__).parent.parent / "docker" / "docker-compose.grfics.yml"
        assert compose_path.exists()

    def test_compose_file_is_valid_yaml(self):
        """The compose file parses as valid YAML."""
        import yaml  # type: ignore
        compose_path = Path(__file__).parent.parent / "docker" / "docker-compose.grfics.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        assert "services" in config
        assert "openplc" in config["services"]

    @pytest.mark.skipif(not _docker_available(), reason="Docker not available")
    def test_compose_config_validates(self):
        """docker compose config succeeds."""
        docker_dir = Path(__file__).parent.parent / "docker"
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.grfics.yml", "config"],
            cwd=str(docker_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Existing contract preservation tests
# ---------------------------------------------------------------------------

class TestExistingContractsPreserved:
    """Verify existing OTB contracts and behaviors remain intact."""

    def test_existing_fixture_still_works(self):
        """The sanitized GRFICS-like fixture still passes ingestion."""
        adapter = JsonTelemetryAdapter()
        dataset = adapter.load(FIXTURE)
        assert dataset.schema == "OTB-INGEST/0.1"
        assert dataset.provenance.source == "grfics"
        assert dataset.provenance.evidence_type == "sanitized_fixture"

    def test_existing_telemetry_contract(self):
        """OTB-TELEMETRY/0.1 contract is unchanged."""
        event = generate("normal", count=10)[0]
        assert event.schema == "OTB-TELEMETRY/0.1"
        assert set(event.to_dict()) == {
            "event_id", "timestamp_ms", "function_code", "address", "value",
            "interval_ms", "latency_ms", "label", "schema",
        }

    def test_all_scenarios_still_generate(self):
        """All five scenarios still generate correctly."""
        from otshield.core import SCENARIOS
        for name in SCENARIOS:
            events = generate(name)
            assert len(events) == 200
            assert all(e.schema == "OTB-TELEMETRY/0.1" for e in events)
