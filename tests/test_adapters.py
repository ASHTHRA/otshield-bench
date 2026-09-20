import subprocess

import pytest

import otshield.adapters.simulation as simulation
from otshield.adapters.simulation import (
    GIB,
    SimulationConfig,
    SimulationContainerAdapter,
)


def _config(tmp_path, **kwargs):
    compose = tmp_path / "compose.yml"
    compose.write_text(
        "services:\n"
        "  simulator:\n"
        "    image: example/simulator\n"
        "networks:\n"
        "  lab:\n"
        "    driver: macvlan\n"
    )

    values = {
        "compose_file": compose,
        "project_name": "otshield-test",
        "parent_interface": "eth0",
        "min_ram_gb": 8,
        "require_macvlan": True,
    }
    values.update(kwargs)
    return SimulationConfig(**values)


def _docker_available(monkeypatch):
    monkeypatch.setattr(
        simulation.shutil,
        "which",
        lambda name: "/usr/bin/docker" if name == "docker" else None,
    )

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Docker Compose version v2",
            stderr="",
        )

    monkeypatch.setattr(simulation.subprocess, "run", fake_run)


def test_preflight_fails_closed_without_docker(tmp_path, monkeypatch):
    cfg = _config(tmp_path)

    monkeypatch.setattr(simulation.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 16 * GIB,
    )
    monkeypatch.setattr(
        simulation,
        "_interface_exists",
        lambda name: True,
    )

    result = SimulationContainerAdapter(cfg).preflight()

    assert result.ready is False
    assert any("Docker CLI" in item for item in result.diagnostics)


def test_preflight_rejects_insufficient_ram(tmp_path, monkeypatch):
    cfg = _config(tmp_path)

    _docker_available(monkeypatch)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 4 * GIB,
    )
    monkeypatch.setattr(
        simulation,
        "_interface_exists",
        lambda name: True,
    )

    result = SimulationContainerAdapter(cfg).preflight()

    assert result.ready is False
    assert any("insufficient RAM" in item for item in result.diagnostics)


def test_preflight_requires_parent_interface(tmp_path, monkeypatch):
    cfg = _config(tmp_path, parent_interface=None)

    _docker_available(monkeypatch)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 16 * GIB,
    )

    result = SimulationContainerAdapter(cfg).preflight()

    assert result.ready is False
    assert any(
        "parent_interface" in item
        for item in result.diagnostics
    )


def test_preflight_rejects_missing_interface(tmp_path, monkeypatch):
    cfg = _config(tmp_path, parent_interface="eth99")

    _docker_available(monkeypatch)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 16 * GIB,
    )
    monkeypatch.setattr(
        simulation,
        "_interface_exists",
        lambda name: False,
    )

    result = SimulationContainerAdapter(cfg).preflight()

    assert result.ready is False
    assert any("eth99" in item for item in result.diagnostics)


def test_preflight_ready_when_requirements_are_mocked(tmp_path, monkeypatch):
    cfg = _config(tmp_path)

    _docker_available(monkeypatch)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 16 * GIB,
    )
    monkeypatch.setattr(
        simulation,
        "_interface_exists",
        lambda name: True,
    )

    result = SimulationContainerAdapter(cfg).preflight()

    assert result.ready is True
    assert result.diagnostics == ()
    assert result.compose_available is True
    assert result.parent_interface_available is True


def test_compose_commands_are_deterministic(tmp_path):
    cfg = _config(tmp_path)
    adapter = SimulationContainerAdapter(cfg)

    assert adapter.command("launch")[-2:] == ("up", "-d")
    assert adapter.command("attach")[-1] == "ps"
    assert adapter.command("stop")[-1] == "down"

    with pytest.raises(ValueError):
        adapter.command("explode")


def test_run_refuses_when_preflight_fails(tmp_path, monkeypatch):
    cfg = _config(tmp_path)

    monkeypatch.setattr(simulation.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        simulation,
        "_total_memory_bytes",
        lambda: 16 * GIB,
    )
    monkeypatch.setattr(
        simulation,
        "_interface_exists",
        lambda name: True,
    )

    adapter = SimulationContainerAdapter(cfg)

    with pytest.raises(RuntimeError, match="preflight failed"):
        adapter.run("launch")
