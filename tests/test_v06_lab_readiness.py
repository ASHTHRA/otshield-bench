"""Offline tests for the v0.6 host readiness gate.

These tests never invoke Docker, open a network socket, or create evidence.
"""
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import v06_lab_readiness as readiness


COMPOSE = """
services:
  openplc:
    image: example/openplc:test
    ports:
      - "502:502"
networks:
  otshield-ics-net:
    driver: bridge
"""


def fake_compose(tmp_path):
    path = tmp_path / "compose.yml"
    path.write_text(COMPOSE)
    return path


def fake_command(args, *, timeout=15):
    if args[-1] == "info":
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    if args[-2:] == ["compose", "version"]:
        return SimpleNamespace(returncode=0, stdout="Docker Compose v2", stderr="")
    if "config" in args:
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    if args[-2:] == ["inspect", "example/openplc:test"]:
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def patch_common(monkeypatch):
    monkeypatch.setattr(readiness.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(readiness, "_python_dependencies", lambda: readiness.Check("python_dependencies", readiness.PASS, "mocked"))
    monkeypatch.setattr(readiness, "_capture_tools", lambda: readiness.Check("capture_tooling", readiness.PASS, "mocked"))
    monkeypatch.setattr(readiness.shutil, "disk_usage", lambda path: SimpleNamespace(free=20 * 1024**3))


def test_default_gate_never_starts_openplc(tmp_path, monkeypatch):
    patch_common(monkeypatch)
    gate = readiness.Readiness(compose_file=fake_compose(tmp_path), runtime=tmp_path / "runtime",
                               runner=fake_command)
    report = gate.run()
    assert report["study_started"] is False
    assert report["study_results_created"] is False
    assert {item["status"] for item in report["checks"]} >= {readiness.NOT_CHECKED}
    assert not list(tmp_path.glob("evidence/**"))


def test_missing_image_is_external_action(tmp_path, monkeypatch):
    patch_common(monkeypatch)
    def command(args, *, timeout=15):
        result = fake_command(args, timeout=timeout)
        if args[-2:] == ["inspect", "example/openplc:test"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="No such image")
        return result
    report = readiness.Readiness(compose_file=fake_compose(tmp_path), runtime=tmp_path / "runtime",
                                 runner=command).run()
    check = next(item for item in report["checks"] if item["name"] == "images")
    assert check["status"] == readiness.EXTERNAL
    assert "example/openplc:test" in check["detail"]


def test_macvlan_requires_parent_interface(tmp_path, monkeypatch):
    patch_common(monkeypatch)
    compose = tmp_path / "compose.yml"
    compose.write_text(COMPOSE.replace("driver: bridge", "driver: macvlan"))
    report = readiness.Readiness(compose_file=compose, runtime=tmp_path / "runtime",
                                 runner=fake_command).run()
    check = next(item for item in report["checks"] if item["name"] == "network_nic_macvlan")
    assert check["status"] == readiness.EXTERNAL
    assert "parent NIC" in check["detail"]


def test_authorized_probe_captures_identity_and_cleans_same_container(tmp_path, monkeypatch):
    patch_common(monkeypatch)
    monkeypatch.setattr(readiness, "_tcp_endpoint", lambda host, port: (True, "mock TCP"))
    monkeypatch.setattr(readiness, "_modbus_fc3", lambda host, port: (True, "mock FC3"))
    calls = []
    def command(args, *, timeout=15):
        calls.append(args)
        if args[-2:] == ["inspect", "--format"]:
            raise AssertionError("unexpected argument ordering")
        if "up" in args:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] == ["/usr/bin/docker", "inspect"] and "{{.Id}}" in args:
            return SimpleNamespace(returncode=0, stdout="a" * 64 + "\n", stderr="")
        if args[:2] == ["/usr/bin/docker", "inspect"] and "{{.Id}} {{.State.Running}}" in args:
            return SimpleNamespace(returncode=0, stdout="a" * 64 + " true\n", stderr="")
        if args[:2] == ["/usr/bin/docker", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="a" * 64 + "\n", stderr="")
        return fake_command(args, timeout=timeout)
    gate = readiness.Readiness(compose_file=fake_compose(tmp_path), runtime=tmp_path / "runtime",
                               authorize_start=True, runner=command)
    report = gate.run()
    assert report["overall"] == readiness.PASS, json.dumps(report, indent=2)
    assert any(item["name"] == "container_identity" and item["status"] == readiness.PASS for item in report["checks"])
    gate.cleanup()
    assert any(call[-3:] == ["rm", "-f", "otshield-openplc"] for call in calls)


def test_cleanup_does_not_remove_replaced_container(tmp_path, monkeypatch):
    patch_common(monkeypatch)
    monkeypatch.setattr(readiness, "_tcp_endpoint", lambda host, port: (True, "mock TCP"))
    monkeypatch.setattr(readiness, "_modbus_fc3", lambda host, port: (True, "mock FC3"))
    responses = iter([SimpleNamespace(returncode=0, stdout="a" * 64 + " true\n", stderr=""),
                      SimpleNamespace(returncode=0, stdout="a" * 64 + " true\n", stderr=""),
                      SimpleNamespace(returncode=0, stdout="b" * 64 + "\n", stderr="")])
    def command(args, *, timeout=15):
        if "image" in args:
            return fake_command(args, timeout=timeout)
        if args[:2] == ["/usr/bin/docker", "inspect"]:
            if "{{.Id}}" in args:
                return next(responses)
            return next(responses)
        return fake_command(args, timeout=timeout)
    gate = readiness.Readiness(compose_file=fake_compose(tmp_path), runtime=tmp_path / "runtime",
                               authorize_start=True, runner=command)
    gate.run()
    gate.cleanup()
    # The replacement identity is not touched; cleanup is identity-scoped.
    assert list(responses) == []


def test_reports_are_machine_and_human_readable(tmp_path):
    report = {"overall": readiness.FAIL, "checks": [{"name": "x", "status": "FAIL", "detail": "bad"}]}
    json_path, markdown_path = readiness.write_reports(report, tmp_path / "report")
    assert json.loads(json_path.read_text())["overall"] == "FAIL"
    assert "**FAIL** `x`" in markdown_path.read_text()


def test_fc3_response_validation(monkeypatch):
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def settimeout(self, value): pass
        def sendall(self, value): self.request = value
        def recv(self, size):
            return {7: b"\x00\x01\x00\x00\x00\x05\x01", 4: b"\x03\x02\x00\x01"}[size]
    monkeypatch.setattr(readiness.socket, "create_connection", lambda address, timeout: Connection())
    assert readiness._modbus_fc3("127.0.0.1", 502)[0] is True


def _wait_gate(monkeypatch, *, endpoints, fc3=None, identities=None):
    gate = readiness.Readiness(compose_file=Path("compose.yml"), port=502,
                               authorize_start=True, service_timeout=3, retry_interval=1)
    gate.started_id = "a" * 64
    gate.sleeper = lambda seconds: None
    clock = iter([0, 0, 1, 2, 3, 4, 5])
    gate.monotonic = lambda: next(clock, 5)
    identity_values = iter(identities or [(gate.started_id, True, "running")] * 8)
    monkeypatch.setattr(gate, "_identity", lambda docker: next(identity_values))
    endpoint_values = iter(endpoints)
    monkeypatch.setattr(readiness, "_tcp_endpoint", lambda host, port: next(endpoint_values))
    monkeypatch.setattr(readiness, "_modbus_fc3", lambda host, port: fc3 or (True, "FC3 ok"))
    gate._wait_for_modbus("docker")
    return gate


def test_service_becomes_ready_after_retries(monkeypatch):
    gate = _wait_gate(monkeypatch, endpoints=[(False, "closed"), (False, "starting"), (True, "open")])
    check = gate.checks[-1]
    assert check.name == "modbus_fc3" and check.status == readiness.PASS
    assert check.evidence["attempts"] == 3


def test_tcp_never_becomes_ready(monkeypatch):
    gate = _wait_gate(monkeypatch, endpoints=[(False, "closed")] * 8)
    assert gate.checks[-1].status == readiness.FAIL
    assert "did not become ready" in gate.checks[-1].detail


def test_tcp_opens_but_fc3_fails(monkeypatch):
    gate = _wait_gate(monkeypatch, endpoints=[(True, "open")] * 8,
                      fc3=(False, "connection reset by peer"))
    assert gate.checks[-1].status == readiness.FAIL
    assert "TCP ready but FC3 failed" in gate.checks[-1].detail


def test_identity_changes_during_wait(monkeypatch):
    gate = _wait_gate(monkeypatch, endpoints=[(False, "closed")],
                      identities=[("a" * 64, True, "running"), ("b" * 64, True, "replaced")])
    assert gate.checks[-2].name == "container_identity"
    assert gate.checks[-2].status == readiness.FAIL
    assert gate.checks[-1].status == readiness.NOT_CHECKED


def test_successful_fc3_readiness(monkeypatch):
    gate = _wait_gate(monkeypatch, endpoints=[(True, "open")], fc3=(True, "FC3 succeeded"))
    assert gate.checks[-1].status == readiness.PASS


def test_compose_port_mapping_is_resolved():
    document = {"services": {"openplc": {"ports": ["${OTSHIELD_OPENPLC_MODBUS_PORT:-1502}:502"]}}}
    assert readiness._compose_host_port(document, {}) == 1502
    assert readiness._compose_host_port(document, {"OTSHIELD_OPENPLC_MODBUS_PORT": "2502"}) == 2502
