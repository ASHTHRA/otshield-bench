"""Fail-closed, evidence-free readiness gate for the replacement v0.6 lab.

The gate checks host and dependency state before a study is created.  It never
creates ``evidence/v06`` and never runs the study runner.  Starting OpenPLC is
an explicit opt-in (``--authorize-start``), uses a unique Compose project, and
removes only the container it started after bounded checks.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import re
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE = REPO / "docker/docker-compose.grfics.yml"
DEFAULT_RUNTIME = REPO / ".otshield-runtime/v06-readiness"
DEFAULT_EVIDENCE = REPO / "evidence/v06"
DEFAULT_DISK_GIB = 10.0
PASS = "PASS"
FAIL = "FAIL"
NOT_CHECKED = "NOT_CHECKED"
EXTERNAL = "EXTERNAL_ACTION_REQUIRED"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {"name": self.name, "status": self.status, "detail": self.detail}
        if self.evidence:
            result["evidence"] = self.evidence
        return result


class ReadinessError(RuntimeError):
    pass


def command(args: list[str], *, timeout: float = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def _parse_compose(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        import yaml
    except ImportError:
        return None, "PyYAML is not installed; Compose structure cannot be parsed offline"
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return None, f"Compose YAML parse failed: {exc}"
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        return None, "Compose file has no services mapping"
    return document, None


def _images(document: dict[str, Any]) -> list[str]:
    return sorted({str(service["image"]) for service in document.get("services", {}).values()
                   if isinstance(service, dict) and service.get("image")})


def _compose_host_port(document: dict[str, Any], environ: Any) -> int | None:
    """Resolve the host port mapped to OpenPLC's container port 502."""
    service = document.get("services", {}).get("openplc", {})
    for mapping in service.get("ports", []) if isinstance(service, dict) else []:
        if isinstance(mapping, dict) and str(mapping.get("target")) == "502":
            return int(mapping["published"])
        value = str(mapping)
        if ":502" not in value:
            continue
        host = value.rsplit(":", 1)[0]
        match = re.fullmatch(r"\$\{([^}:]+)(?::-([^}]+))?\}", host)
        if match:
            host = environ.get(match.group(1), match.group(2) or "")
        host = host.rsplit(":", 1)[-1]
        try:
            return int(host)
        except ValueError:
            return None
    return None


def _network_requirements(document: dict[str, Any], interface: str | None) -> Check:
    networks = document.get("networks", {})
    drivers = sorted({str(value.get("driver", "bridge")) for value in networks.values()
                      if isinstance(value, dict)})
    macvlan = [name for name, value in networks.items()
               if isinstance(value, dict) and value.get("driver") == "macvlan"]
    if not macvlan:
        return Check("network_nic_macvlan", PASS,
                     f"Compose declares {', '.join(drivers) or 'default'} network; macvlan/NIC not required by this file",
                     {"drivers": drivers, "macvlan_networks": []})
    if not interface:
        return Check("network_nic_macvlan", EXTERNAL,
                     "macvlan is configured but no parent NIC was supplied", {"networks": macvlan})
    if not Path("/sys/class/net", interface).exists():
        return Check("network_nic_macvlan", FAIL,
                     f"configured macvlan parent NIC does not exist: {interface}", {"interface": interface})
    return Check("network_nic_macvlan", PASS,
                 f"macvlan parent NIC exists: {interface}", {"interface": interface, "networks": macvlan})


def _tcp_endpoint(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP endpoint accepted a connection at {host}:{port}"
    except OSError as exc:
        return False, f"TCP endpoint is not ready at {host}:{port}: {exc}"


def _modbus_fc3(host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    """Perform one bounded Modbus/TCP FC3 request and inspect its response."""
    transaction = 1
    request = transaction.to_bytes(2, "big") + b"\x00\x00\x00\x06\x01\x03\x00\x00\x00\x01"
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(request)
            header = conn.recv(7)
            if len(header) != 7:
                return False, "Modbus response header was incomplete"
            length = int.from_bytes(header[4:6], "big")
            if length < 3 or length > 260:
                return False, f"invalid Modbus response length: {length}"
            body = conn.recv(length - 1)
            if len(body) < 2:
                return False, "Modbus response body was incomplete"
            if header[6] != 1 or body[0] != 3:
                return False, f"unexpected unit/function in response: {header[6:7].hex()}{body[:1].hex()}"
            if len(body) < 4 or body[1] != 2:
                return False, "FC3 response did not contain one register"
            return True, "bounded read-only Modbus FC3 succeeded"
    except (OSError, ValueError) as exc:
        return False, f"Modbus FC3 endpoint check failed: {exc}"


@contextmanager
def _lock_available(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _check_writable(path: Path) -> Check:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".readiness-write-probe"
        probe.write_text("readiness probe\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("writable_paths", FAIL, f"path is not writable: {path}: {exc}")
    return Check("writable_paths", PASS, f"runtime path is writable: {path}")


def _check_evidence_parent(path: Path) -> Check:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".readiness-evidence-write-probe"
        probe.write_text("readiness probe\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("evidence_path", FAIL, f"evidence parent is not writable: {parent}: {exc}")
    return Check("evidence_path", PASS, f"evidence parent is writable; no evidence directory was created: {parent}")


def _check_disk(path: Path, minimum_gib: float) -> Check:
    try:
        free = shutil.disk_usage(path).free
    except OSError as exc:
        return Check("disk_space", FAIL, f"disk usage unavailable: {exc}")
    required = int(minimum_gib * 1024 ** 3)
    if free < required:
        return Check("disk_space", FAIL, f"only {free / 1024**3:.2f} GiB free; requires {minimum_gib:g} GiB")
    return Check("disk_space", PASS, f"{free / 1024**3:.2f} GiB free (conservative threshold {minimum_gib:g} GiB)",
                 {"free_bytes": free, "threshold_bytes": required})


def _python_dependencies() -> Check:
    missing = []
    for module in ("yaml", "pymodbus", "scipy", "sklearn"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        return Check("python_dependencies", FAIL, "missing required Python packages: " + ", ".join(missing))
    return Check("python_dependencies", PASS, "PyYAML, pymodbus, SciPy and scikit-learn import successfully")


def _capture_tools() -> Check:
    tools = {name: shutil.which(name) for name in ("tcpdump", "tshark")}
    available = [name for name, path in tools.items() if path]
    if not available:
        return Check("capture_tooling", FAIL, "neither tcpdump nor tshark is available", tools)
    return Check("capture_tooling", PASS, "capture tooling available: " + ", ".join(available), tools)


class Readiness:
    def __init__(self, *, compose_file: Path = DEFAULT_COMPOSE, runtime: Path = DEFAULT_RUNTIME,
                 evidence: Path = DEFAULT_EVIDENCE, interface: str | None = None,
                 authorize_start: bool = False, host: str = "127.0.0.1", port: int | None = None,
                 project: str | None = None, minimum_disk_gib: float = DEFAULT_DISK_GIB,
                 runner: Callable[..., subprocess.CompletedProcess[str]] = command,
                 service_timeout: float = 60.0, retry_interval: float = 2.0,
                 sleeper: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self.compose_file, self.runtime, self.evidence = compose_file, runtime, evidence
        self.interface, self.authorize_start, self.host, self.port = interface, authorize_start, host, port
        self.project = project or f"otshield-readiness-{os.getpid()}"
        self.minimum_disk_gib, self.runner = minimum_disk_gib, runner
        self.service_timeout, self.retry_interval = service_timeout, retry_interval
        self.sleeper, self.monotonic = sleeper, monotonic
        self.checks: list[Check] = []
        self.started_id: str | None = None
        self.started = False
        self.network_name = f"{self.project}_otshield-ics-net"

    def _run(self, args: list[str], timeout: float = 15) -> subprocess.CompletedProcess[str]:
        return self.runner(args, timeout=timeout)

    def _identity(self, docker: str) -> tuple[str | None, bool, str]:
        result = self._run([docker, "inspect", "--format", "{{.Id}} {{.State.Running}}", "otshield-openplc"])
        fields = result.stdout.strip().split()
        if result.returncode or len(fields) != 2:
            return None, False, result.stderr.strip() or "OpenPLC container identity could not be inspected"
        return fields[0], fields[1].lower() == "true", "OpenPLC identity is present and running"

    def _cleanup_stale_networks(self, docker: str) -> None:
        """Remove only empty networks created by earlier readiness invocations."""
        listed = self._run([docker, "network", "ls", "--format", "{{.Name}} {{.Labels}}"])
        if listed.returncode:
            return
        for line in listed.stdout.splitlines():
            name, _, labels = line.partition(" ")
            if not name.startswith("otshield-readiness-") or "com.docker.compose.project=otshield-readiness-" not in labels:
                continue
            inspected = self._run([docker, "network", "inspect", name, "--format", "{{json .Containers}}"])
            if inspected.returncode == 0 and inspected.stdout.strip() in {"{}", "null", ""}:
                self._run([docker, "network", "rm", name], timeout=30)

    def _docker_checks(self, document: dict[str, Any]) -> None:
        docker = shutil.which("docker")
        if not docker:
            self.checks.append(Check("docker_cli", FAIL, "Docker CLI is not available on PATH"))
            for name in ("docker_daemon", "docker_compose", "compose_parse", "images"):
                self.checks.append(Check(name, NOT_CHECKED, "Docker CLI prerequisite is missing"))
            return
        self.checks.append(Check("docker_cli", PASS, f"Docker CLI found at {docker}"))
        info = self._run([docker, "info"], timeout=20)
        self.checks.append(Check("docker_daemon", PASS, "Docker daemon is reachable") if info.returncode == 0 else
                           Check("docker_daemon", FAIL, info.stderr.strip() or "Docker daemon is unreachable"))
        compose = self._run([docker, "compose", "version"])
        self.checks.append(Check("docker_compose", PASS, compose.stdout.strip() or "Docker Compose is available") if compose.returncode == 0 else
                           Check("docker_compose", FAIL, compose.stderr.strip() or "Docker Compose is unavailable"))
        parsed = self._run([docker, "compose", "-f", str(self.compose_file), "config", "--quiet"])
        self.checks.append(Check("compose_parse", PASS, "Docker Compose accepted the required file") if parsed.returncode == 0 else
                           Check("compose_parse", FAIL, parsed.stderr.strip() or "Docker Compose rejected the required file"))
        missing = []
        for image in _images(document):
            inspected = self._run([docker, "image", "inspect", image])
            if inspected.returncode:
                missing.append(image)
        self.checks.append(Check("images", PASS, "all required Compose images are available", {"images": _images(document)}) if not missing else
                           Check("images", EXTERNAL, "required images are missing: " + ", ".join(missing), {"missing": missing}))

    def _start_and_probe(self) -> None:
        if not self.authorize_start:
            self.checks.append(Check("openplc_start", NOT_CHECKED, "OpenPLC start was not authorized; use --authorize-start explicitly"))
            self.checks.append(Check("container_identity", NOT_CHECKED, "no readiness-owned OpenPLC container was started"))
            self.checks.append(Check("modbus_fc3", NOT_CHECKED, "no endpoint probe was attempted"))
            return
        blocked = [check for check in self.checks if check.status in {FAIL, EXTERNAL}]
        if blocked:
            names = ", ".join(check.name for check in blocked)
            self.checks.append(Check("openplc_start", NOT_CHECKED,
                                     f"startup withheld until prerequisite checks pass: {names}"))
            self.checks.append(Check("container_identity", NOT_CHECKED, "OpenPLC was not started"))
            self.checks.append(Check("modbus_fc3", NOT_CHECKED, "OpenPLC was not started"))
            return
        docker = shutil.which("docker")
        if not docker:
            self.checks.append(Check("openplc_start", NOT_CHECKED, "Docker CLI prerequisite is missing"))
            return
        existing = self._run([docker, "ps", "-a", "--filter", "name=^/otshield-openplc$", "--format", "{{.ID}}"])
        if existing.returncode == 0 and existing.stdout.strip():
            self.checks.append(Check("openplc_start", EXTERNAL,
                                     "otshield-openplc already exists; refusing to start or clean an unrelated container",
                                     {"existing_id": existing.stdout.strip()}))
            self.checks.append(Check("container_identity", NOT_CHECKED, "existing container is not readiness-owned"))
            self.checks.append(Check("modbus_fc3", NOT_CHECKED, "FC3 probe withheld for unrelated container"))
            return
        self._cleanup_stale_networks(docker)
        result = self._run([docker, "compose", "-f", str(self.compose_file), "-p", self.project, "up", "-d", "openplc"], timeout=120)
        if result.returncode:
            self.checks.append(Check("openplc_start", FAIL, result.stderr.strip() or "OpenPLC could not be started"))
            return
        self.started = True
        identity, running, identity_detail = self._identity(docker)
        if identity is None or not running:
            self.checks.append(Check("openplc_start", FAIL, "OpenPLC did not report a running state"))
            self.checks.append(Check("container_identity", FAIL, identity_detail))
            return
        self.started_id = identity
        self.checks.append(Check("openplc_start", PASS, "OpenPLC was started by this readiness check"))
        self.checks.append(Check("container_identity", PASS, "OpenPLC container identity captured", {"id": self.started_id}))
        self._wait_for_modbus(docker)

    def _wait_for_modbus(self, docker: str) -> None:
        if self.port is None:
            self.checks.append(Check("modbus_fc3", FAIL, "host Modbus port could not be resolved from Compose mapping"))
            return
        deadline = self.monotonic() + self.service_timeout
        attempts = 0
        last_detail = "service did not become ready"
        while True:
            attempts += 1
            identity, running, identity_detail = self._identity(docker)
            if identity != self.started_id or not running:
                self.checks.append(Check("container_identity", FAIL,
                                         f"OpenPLC identity changed or stopped during Modbus wait: {identity_detail}",
                                         {"expected_id": self.started_id, "observed_id": identity, "running": running}))
                self.checks.append(Check("modbus_fc3", NOT_CHECKED, "FC3 probe withheld after lifecycle identity failure"))
                return
            endpoint_ok, endpoint_detail = _tcp_endpoint(self.host, self.port)
            if endpoint_ok:
                ok, detail = _modbus_fc3(self.host, self.port)
                if ok:
                    self.checks.append(Check("modbus_fc3", PASS,
                                             f"{detail}; endpoint readiness succeeded after {attempts} attempt(s)",
                                             {"host": self.host, "port": self.port, "attempts": attempts}))
                    return
                last_detail = f"TCP ready but FC3 failed: {detail}"
            else:
                last_detail = endpoint_detail
            if self.monotonic() >= deadline:
                self.checks.append(Check("modbus_fc3", FAIL,
                                         f"Modbus service did not become ready within {self.service_timeout:g}s after {attempts} attempt(s): {last_detail}",
                                         {"host": self.host, "port": self.port, "attempts": attempts,
                                          "timeout_seconds": self.service_timeout}))
                return
            self.sleeper(min(self.retry_interval, max(0.0, deadline - self.monotonic())))

    def run(self) -> dict[str, Any]:
        if not self.compose_file.is_file():
            self.checks.append(Check("compose_file", FAIL, f"required Compose file is missing: {self.compose_file}"))
            document = None
        else:
            document, error = _parse_compose(self.compose_file)
            self.checks.append(Check("compose_file", PASS, f"required Compose file exists: {self.compose_file}") if not error else
                               Check("compose_file", FAIL, error))
        if document is not None and self.port is None:
            self.port = _compose_host_port(document, os.environ)
        self.checks.append(_check_writable(self.runtime))
        self.checks.append(_check_evidence_parent(self.evidence))
        self.checks.append(_check_disk(self.runtime, self.minimum_disk_gib))
        with _lock_available(self.runtime / "v06-lab.lock") as available:
            self.checks.append(Check("lab_lock", PASS, "v0.6 lab lock is available") if available else
                               Check("lab_lock", FAIL, "v0.6 lab lock is currently held by another process"))
        self.checks.append(_python_dependencies())
        self.checks.append(_capture_tools())
        if document is not None:
            self._docker_checks(document)
            self.checks.append(_network_requirements(document, self.interface))
        else:
            for name in ("docker_cli", "docker_daemon", "docker_compose", "compose_parse", "images", "network_nic_macvlan"):
                self.checks.append(Check(name, NOT_CHECKED, "Compose file prerequisite failed"))
        self._start_and_probe()
        statuses = {check.status for check in self.checks}
        overall = FAIL if FAIL in statuses else EXTERNAL if EXTERNAL in statuses else NOT_CHECKED if NOT_CHECKED in statuses else PASS
        return {"schema": "OTB-V06-LAB-READINESS/0.1", "overall": overall,
                "authorize_start": self.authorize_start, "compose_file": str(self.compose_file),
                "checks": [check.as_dict() for check in self.checks],
                "study_started": False, "study_results_created": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat()}

    def cleanup(self) -> None:
        if not self.started:
            return
        docker = shutil.which("docker")
        if not docker:
            return
        current = self._run([docker, "inspect", "--format", "{{.Id}}", "otshield-openplc"])
        if self.started_id and current.returncode == 0 and current.stdout.strip() == self.started_id:
            self._run([docker, "rm", "-f", "otshield-openplc"], timeout=30)
        # Compose names this network from our unique project.  Remove only that
        # exact network after the owned container is gone.
        self._run([docker, "network", "rm", self.network_name], timeout=30)


def write_reports(report: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=False)
    json_path = directory / "readiness.json"
    md_path = directory / "readiness.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# v0.6 Lab Readiness", "", f"Overall: **{report['overall']}**", "",
             "This report is a host readiness check. It is not laboratory evidence.", ""]
    for check in report["checks"]:
        lines.append(f"- **{check['status']}** `{check['name']}` — {check['detail']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--interface", help="macvlan parent NIC when the Compose file requires one")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None,
                        help="host Modbus port (defaults to the Compose mapping)")
    parser.add_argument("--project", help="unique readiness Compose project name")
    parser.add_argument("--min-disk-gib", type=float, default=DEFAULT_DISK_GIB)
    parser.add_argument("--authorize-start", action="store_true", help="explicitly start OpenPLC for a bounded FC3 readiness probe")
    args = parser.parse_args(argv)
    gate = Readiness(compose_file=args.compose_file, interface=args.interface, host=args.host,
                     port=args.port, project=args.project, authorize_start=args.authorize_start,
                     minimum_disk_gib=args.min_disk_gib)
    report = gate.run()
    try:
        report_dir = args.report_dir or DEFAULT_RUNTIME / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path, md_path = write_reports(report, report_dir)
    finally:
        gate.cleanup()
    print(f"LAB READINESS: {report['overall']}")
    print(f"Machine-readable report: {json_path}")
    print(f"Human-readable summary: {md_path}")
    return 0 if report["overall"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
