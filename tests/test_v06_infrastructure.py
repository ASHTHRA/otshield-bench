"""Host lock and shell function harnesses only: no Docker or laboratory traffic."""
import sys

import pytest

if sys.platform != "linux":
    pytest.skip("OTShield v0.6 lab lifecycle/locking tests require POSIX/Linux semantics",
                allow_module_level=True)

import fcntl
import importlib.util
import os
from pathlib import Path
import re
import signal
import subprocess

REPO = Path(__file__).resolve().parents[1]
WORKER = (REPO / "scripts/run_v06_lab_worker.sh").read_text()


@pytest.fixture
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("infra_runner", REPO / "scripts/run_v06_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCK_PATH", tmp_path / "runtime/lab.lock")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/fake/docker")
    return module


def assert_locked(runner):
    with pytest.raises(runner.StudyLocked):
        with runner.execution_lock(runner.LOCK_PATH):
            pytest.fail("lock is not exclusive")


def assert_released(runner):
    with runner.execution_lock(runner.LOCK_PATH):
        pass


@pytest.mark.parametrize("flags", [[], ["--dry-run"], ["--preflight"]])
def test_preflight_never_acquires_lock(runner, tmp_path, monkeypatch, flags):
    def forbidden(*args, **kwargs):
        pytest.fail("preflight touched lock or subprocess")
    monkeypatch.setattr(runner, "execution_lock", forbidden)
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    monkeypatch.setattr(runner.subprocess, "check_output", forbidden)
    root = tmp_path / "no-evidence"
    monkeypatch.setattr(sys, "argv", ["runner", *flags, "--output", str(root)])
    assert runner.main() == 0
    assert not root.exists()
    assert not runner.LOCK_PATH.exists()


def test_real_flock_excludes_another_process_and_allows_stale_file(runner):
    with runner.execution_lock(runner.LOCK_PATH):
        code = '''import fcntl, sys
with open(sys.argv[1], "a+") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(42)
sys.exit(0)
'''
        result = subprocess.run([sys.executable, "-c", code, str(runner.LOCK_PATH)], timeout=5)
        assert result.returncode == 42
    assert runner.LOCK_PATH.exists()
    assert_released(runner)


def test_concurrent_runner_refused_before_output_or_subprocess(runner, tmp_path, monkeypatch, capsys):
    root = tmp_path / "refused"
    monkeypatch.setattr(sys, "argv", ["runner", "--execute-lab", "--output", str(root)])
    def forbidden(*args, **kwargs):
        pytest.fail("contender launched a subprocess")
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    monkeypatch.setattr(runner.subprocess, "check_output", forbidden)
    with runner.execution_lock(runner.LOCK_PATH):
        with pytest.raises(SystemExit) as exc:
            runner.main()
        assert exc.value.code == 2
        assert not root.exists()
        assert_locked(runner)
    assert "another v0.6 lab execution holds the lock" in capsys.readouterr().err


@pytest.mark.parametrize("outcome", ["success", "failure", "launch_error", "wait_error",
                                     "sigint", "sigterm", "signal_during_launch", "finalize_error"])
def test_execution_holds_lock_through_finalization_and_releases(
        runner, tmp_path, monkeypatch, outcome):
    root = tmp_path / "synthetic-output"
    monkeypatch.setattr(sys, "argv", ["runner", "--execute-lab", "--output", str(root)])
    launches, waits, kills, failures = [], [], [], []
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}

    def provenance(args, **kwargs):
        assert not root.exists()  # Lock is already held before directory creation.
        assert_locked(runner)
        return "synthetic-commit" if args[1] == "rev-parse" else ""
    monkeypatch.setattr(runner.subprocess, "check_output", provenance)

    class FakeWorker:
        args = ["synthetic-worker"]
        pid = 123456789

        def __init__(self, *args, **kwargs):
            launches.append(kwargs)
            assert_locked(runner)
            fd = int(kwargs["env"]["V06_LOCK_FD"])
            assert kwargs["pass_fds"] == (fd,)
            assert os.fstat(fd).st_ino == runner.LOCK_PATH.stat().st_ino
            if outcome == "launch_error":
                raise OSError("synthetic launch failure")
            if outcome == "signal_during_launch":
                signal.raise_signal(signal.SIGTERM)

        def wait(self, timeout=None):
            waits.append(timeout)
            assert_locked(runner)
            if timeout is None:
                if outcome == "wait_error":
                    raise RuntimeError("synthetic wait failure")
                if outcome in ("sigint", "sigterm"):
                    signal.raise_signal(signal.SIGINT if outcome == "sigint" else signal.SIGTERM)
                return 1 if outcome == "failure" else 0
            # Repeated interrupts must not skip final accounting.
            signal.raise_signal(signal.SIGTERM)
            signal.raise_signal(signal.SIGINT)
            return 0

    monkeypatch.setattr(runner.subprocess, "Popen", FakeWorker)
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: kills.append((pid, sig)))

    def finalize(root, commit, failure):
        assert_locked(runner)
        failures.append(failure)
        if outcome == "finalize_error":
            raise OSError("synthetic accounting failure")
        return {"status": "incomplete" if failure else "completed", "completed_condition_runs": 0}
    monkeypatch.setattr(runner, "finalize", finalize)
    if outcome == "finalize_error":
        with pytest.raises(OSError, match="accounting failure"):
            runner.main()
    else:
        assert runner.main() == (0 if outcome == "success" else 1)
    assert len(launches) == 1  # Never retry a failed worker.
    assert len(failures) == 1
    assert bool(kills) == (outcome in ("wait_error", "sigint", "sigterm", "signal_during_launch"))
    assert_released(runner)
    assert {s: signal.getsignal(s) for s in handlers} == handlers


def shell_function(name):
    return re.search(r"^" + name + r"\(\) \{\n.*?^\}", WORKER, re.M | re.S).group()


@pytest.mark.parametrize("observed,running,status,expected", [
    ("", "", 1, False),
    ("b" * 64, "true", 0, False),
    ("a" * 64, "false", 0, False),
    ("a" * 64, "true", 0, True),
    ("a" * 64, "garbage", 0, False),
    ("", "", 0, False),
    ("a" * 64, "true\nextra", 0, False),
])
def test_identity_guard_uses_fake_docker(observed, running, status, expected):
    # Only extract the guard definition. Never execute/source the worker.
    script = '''set -Eeuo pipefail
docker() {
    [[ "$*" == "inspect --format {{.Id}} {{.State.Running}} otshield-openplc" ]] || exit 97
    printf '%s %s\\n' "$FAKE_ID" "$FAKE_RUNNING"
    return "$FAKE_STATUS"
}
''' + shell_function("verify_openplc_identity") + "\nverify_openplc_identity\necho PASSED\n"
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
        env={**os.environ, "OPENPLC_EXPECTED_ID": "a" * 64, "FAKE_ID": observed,
             "FAKE_RUNNING": running, "FAKE_STATUS": str(status)}, timeout=5)
    assert (result.returncode == 0) is expected
    if expected:
        assert result.stdout == "PASSED\n"
    else:
        assert "PASSED" not in result.stdout
        assert "INFRASTRUCTURE_FAILURE: OpenPLC lifecycle identity mismatch" in result.stderr
        assert "EXPECTED_OPENPLC_ID=" + "a" * 64 in result.stderr
        assert f"OBSERVED_OPENPLC_ID={observed if status == 0 and observed else 'missing'}" in result.stderr
        assert f"OBSERVED_RUNNING_STATE={running.splitlines()[0] if status == 0 and running else 'missing'}" in result.stderr


@pytest.mark.parametrize("ownership", ["held", "unlocked", "wrong_inode", "foreign_owner", "missing_fd"])
def test_worker_ownership_guard_without_worker_or_docker(tmp_path, ownership):
    runtime = tmp_path / ".otshield-runtime"
    runtime.mkdir()
    path = runtime / "v06-lab.lock"
    script = shell_function("verify_execution_lock") + "\nverify_execution_lock\n"
    with path.open("a+") as owner, path.open("a+") as foreign, (tmp_path / "other").open("a+") as other:
        if ownership in ("held", "foreign_owner", "wrong_inode"):
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd = {"foreign_owner": foreign.fileno(), "wrong_inode": other.fileno(),
              "missing_fd": 9999}.get(ownership, owner.fileno())
        result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
            env={**os.environ, "V06_LOCK_FD": str(fd),
                 "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]},
            pass_fds=() if ownership == "missing_fd" else (fd,), capture_output=True, text=True, timeout=5)
        assert (result.returncode == 0) == (ownership == "held")
        if ownership != "held":
            assert "study execution lock ownership required" in result.stderr
    assert WORKER.index("\nverify_execution_lock\n") < WORKER.index('mkdir -p "$ROOT"')
    assert WORKER.index("\nverify_execution_lock\n") < WORKER.index("trap cleanup_all EXIT")


def test_frozen_worker_design_and_lifecycle_checkpoints():
    from otshield.paired_v06 import load_calibration
    from otshield.study_v06 import CONDITIONS
    assert re.findall(r"^TRIALS=.*$", WORKER, re.M) == ["TRIALS=25"]
    conditions = re.search(r"CONDITIONS=\(\n(.*?)\n\)", WORKER, re.S).group(1)
    assert re.findall(r'"([^"]+)"', conditions) == [":".join(map(str, c)) for c in CONDITIONS]
    trial = WORKER.index('for TRIAL in $(seq 1 "$TRIALS")')
    condition = WORKER.index('for STEP in $(seq 0 $((COUNT - 1)))')
    assert WORKER.count("up -d openplc") == 1
    assert trial < WORKER.index("up -d openplc") < condition
    assert WORKER.count('        normalize_capture \\\n') == 1
    assert WORKER.count("scripts/evaluate_v06_paired.py") == 1
    assert WORKER.count("exec tcpdump") == 1
    assert 'OFFSET=$(( (TRIAL - 1) % COUNT ))' in WORKER
    assert 'INDEX=$(( (STEP + OFFSET) % COUNT ))' in WORKER
    assert '--network container:otshield-openplc' in WORKER
    assert '"threshold_ms":\n            50.0' in WORKER
    assert load_calibration(REPO / "research/v0.6_calibration.json")["calibration"]["threshold_ms"] == 100.23721899414062
    assert not re.search(r"\b(retry|retries)\b", WORKER)
    assert 'while ' not in WORKER[trial:]
    assert 'continue' not in WORKER[trial:]
    cleanup = shell_function("cleanup_all")
    assert "otshield-resilience-client" in cleanup and "otshield-server-capture" in cleanup
    assert 'down -v' in cleanup
    assert not re.search(r"prune|--filter|docker (ps|kill)", cleanup)
    points = [WORKER.index("    wait_for_openplc\n"), condition,
              WORKER.index("        docker run -d --rm"), WORKER.index("        run_client "),
              WORKER.index("        sleep 1", WORKER.index("        run_client ")),
              WORKER.index("        normalize_capture "), WORKER.index("        python scripts/evaluate_v06_paired.py")]
    checks = [m.start() for m in re.finditer(r"^ +verify_openplc_identity$", WORKER, re.M)]
    assert len(checks) == 7
    assert points[0] < checks[0] < points[1] < checks[1] < checks[2] < points[2]
    assert points[2] < checks[3] < points[3] < checks[4] < points[4]
    assert points[4] < checks[5] < points[5] < checks[6] < points[6]


def test_inherited_descriptor_retains_ownership_until_child_exits(runner):
    child = None
    try:
        with runner.execution_lock(runner.LOCK_PATH) as lock:
            # A harmless Python child stands in for a worker performing cleanup.
            child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                     stdin=subprocess.PIPE, pass_fds=(lock.fileno(),))
        assert_locked(runner)
        child.communicate(timeout=5)
        assert child.returncode == 0
        assert_released(runner)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.communicate(timeout=5)


def test_worker_termination_timeout_escalates_and_reaps(runner, monkeypatch):
    calls = []
    class FakeWorker:
        pid = 123456789
        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired("synthetic-worker", timeout)
            return -signal.SIGKILL
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: calls.append(("kill", sig)))
    runner.stop_worker(FakeWorker())
    assert calls == [("kill", signal.SIGTERM), ("wait", 30),
                     ("kill", signal.SIGKILL), ("wait", None)]


@pytest.mark.parametrize("client_status", [0, 17])
def test_client_return_always_checks_identity_before_processing(client_status):
    start = WORKER.index("        CLIENT_STATUS=0")
    end = WORKER.index("        sleep 1", start)
    # Execute only this small call/check block with shell function mocks.
    harness = '''set -Eeuo pipefail
NETWORK=synthetic DELAY=0 JITTER=0 LOSS=0
run_client() { echo CLIENT; return "$CLIENT_EXIT"; }
verify_openplc_identity() { echo GUARD; return 1; }
''' + WORKER[start:end] + "echo MUST_NOT_PROCESS\n"
    result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                            env={**os.environ, "CLIENT_EXIT": str(client_status)}, timeout=5)
    assert result.returncode == 1
    assert result.stdout.splitlines() == ["CLIENT", "GUARD"]
