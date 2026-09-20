"""Fail-closed configuration and preflight for an optional GRFICS simulation.

This module does not claim that a GRFICS/OpenPLC lab has been executed.
It only validates prerequisites and constructs deterministic Docker Compose
commands for a separately authorized local research environment.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


GIB = 1024 ** 3


@dataclass(frozen=True)
class SimulationConfig:
    """Configuration for an optional local simulation environment."""

    compose_file: Path = Path("docker/docker-compose.grfics.yml")
    project_name: str = "otshield-grfics"
    parent_interface: str | None = None
    min_ram_gb: float = 8.0
    require_macvlan: bool = True

    def __post_init__(self):
        if not self.project_name.strip():
            raise ValueError("project_name must be nonempty")
        if self.min_ram_gb <= 0:
            raise ValueError("min_ram_gb must be positive")


@dataclass(frozen=True)
class SimulationPreflight:
    ready: bool
    diagnostics: tuple[str, ...]
    docker_path: str | None
    compose_available: bool
    total_ram_bytes: int | None
    parent_interface_available: bool


def _total_memory_bytes() -> int | None:
    """Read total Linux/WSL memory without adding a dependency."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _interface_exists(name: str) -> bool:
    return Path("/sys/class/net", name).exists()


def _compose_uses_macvlan(path: Path) -> bool:
    try:
        text = path.read_text()
    except OSError:
        return False
    return "driver: macvlan" in text or "driver:macvlan" in text.replace(" ", "")


class SimulationContainerAdapter:
    """Validate and describe an optional Docker-based simulation.

    Commands are never executed by preflight().  run() is explicit and refuses
    to proceed unless every configured prerequisite passes.
    """

    def __init__(self, config: SimulationConfig | None = None):
        self.config = config or SimulationConfig()

    def preflight(self) -> SimulationPreflight:
        diagnostics: list[str] = []
        cfg = self.config
        compose_file = Path(cfg.compose_file)

        if not compose_file.is_file():
            diagnostics.append(
                f"compose file is missing: {compose_file}"
            )

        docker_path = shutil.which("docker")
        compose_available = False

        if docker_path is None:
            diagnostics.append("Docker CLI is not installed or not on PATH")
        else:
            try:
                result = subprocess.run(
                    [docker_path, "compose", "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                compose_available = result.returncode == 0
                if not compose_available:
                    diagnostics.append(
                        "Docker Compose plugin is unavailable"
                    )
            except (OSError, subprocess.TimeoutExpired):
                diagnostics.append(
                    "Docker Compose availability could not be verified"
                )

        total_ram = _total_memory_bytes()
        minimum = int(cfg.min_ram_gb * GIB)

        if total_ram is None:
            diagnostics.append(
                "host RAM could not be determined; refusing to assume capacity"
            )
        elif total_ram < minimum:
            diagnostics.append(
                f"insufficient RAM: requires at least {cfg.min_ram_gb:g} GiB"
            )

        interface_available = False

        if cfg.require_macvlan:
            if not cfg.parent_interface:
                diagnostics.append(
                    "macvlan parent_interface is not configured"
                )
            else:
                interface_available = _interface_exists(
                    cfg.parent_interface
                )
                if not interface_available:
                    diagnostics.append(
                        f"required NIC does not exist: {cfg.parent_interface}"
                    )

            if compose_file.is_file() and not _compose_uses_macvlan(
                compose_file
            ):
                diagnostics.append(
                    "compose configuration is not configured for macvlan"
                )
        elif cfg.parent_interface:
            interface_available = _interface_exists(cfg.parent_interface)

        return SimulationPreflight(
            ready=not diagnostics,
            diagnostics=tuple(diagnostics),
            docker_path=docker_path,
            compose_available=compose_available,
            total_ram_bytes=total_ram,
            parent_interface_available=interface_available,
        )

    def command(self, action: str) -> tuple[str, ...]:
        """Return a deterministic Docker Compose command without executing it."""
        prefix = (
            "docker",
            "compose",
            "-f",
            str(self.config.compose_file),
            "-p",
            self.config.project_name,
        )

        commands = {
            "launch": prefix + ("up", "-d"),
            "attach": prefix + ("ps",),
            "status": prefix + ("ps",),
            "stop": prefix + ("down",),
        }

        try:
            return commands[action]
        except KeyError as exc:
            raise ValueError(
                "action must be launch, attach, status, or stop"
            ) from exc

    def run(self, action: str) -> subprocess.CompletedProcess:
        """Explicitly execute a compose action only after successful preflight."""
        result = self.preflight()

        if not result.ready:
            raise RuntimeError(
                "simulation preflight failed: "
                + "; ".join(result.diagnostics)
            )

        completed = subprocess.run(
            self.command(action),
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            detail = completed.stderr.strip() or "Docker Compose command failed"
            raise RuntimeError(detail)

        return completed
