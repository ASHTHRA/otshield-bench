#!/usr/bin/env python3
"""Preflight by default; --execute-lab explicitly starts the isolated 25-trial lab."""
import argparse
from contextlib import contextmanager
import fcntl
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import signal
import subprocess

from otshield.paired_v06 import load_calibration
from otshield.study_v06 import finalize, plan, write_json

REPO = Path(__file__).resolve().parents[1]
LOCK_PATH = REPO / ".otshield-runtime/v06-lab.lock"


class StudyLocked(RuntimeError):
    pass


@contextmanager
def execution_lock(path):
    """Keep the inode and descriptor stable; stale file presence is harmless."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StudyLocked(f"another v0.6 lab execution holds the lock: {path}") from None
        # Close, never unlink or explicitly unlock: an inherited worker descriptor
        # must retain ownership until its EXIT cleanup finishes, even if we die.
        yield lock


@contextmanager
def execution_signals():
    state = {"launching": False, "signal": None}
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def interrupted(signum, frame):
        state["signal"] = signum
        # A second signal must not interrupt worker shutdown or final accounting.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        if not state["launching"]:
            raise KeyboardInterrupt(f"received signal {signum}")

    try:
        for sig in previous:
            signal.signal(sig, interrupted)
        yield state
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def stop_worker(process):
    """Wait for scoped worker cleanup before releasing ownership."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def execute_lab(args, parser, calibration, schedule, lock, signals):
    print(f"Execution lock: {LOCK_PATH}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (args.output or REPO / "evidence/v06" / stamp).resolve()
    # New study output must never overwrite or be nested in historical evidence.
    historical = (REPO / "evidence/repeatability").resolve()
    if root == historical or historical in root.parents:
        parser.error("historical evidence is immutable")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], text=True)
    if dirty.strip():
        parser.error("commit implementation changes before laboratory execution for reproducible provenance")
    root.mkdir(parents=True, exist_ok=False)
    failure = None
    process = None
    worker_finished = False
    try:
        shutil.copyfile(calibration, root / "calibration.json")
        shutil.copyfile(REPO / "research/v0.6_experiment_protocol.md", root / "experiment_protocol.md")
        write_json(root / "execution.json", {"execution_git_commit": commit, "schedule": schedule})
        with (root / "execution.log").open("w") as log:
            print(f"Execution lock: {LOCK_PATH}", file=log, flush=True)
            # Defer a signal during Popen until its process handle is assigned.
            signals["launching"] = True
            try:
                process = subprocess.Popen(["bash", "scripts/run_v06_lab_worker.sh"],
                    env={**os.environ, "V06_LAB_AUTHORIZED": "1", "V06_ROOT": str(root),
                         "V06_STAMP": stamp, "V06_LOCK_FD": str(lock.fileno())},
                    pass_fds=(lock.fileno(),), stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
            finally:
                signals["launching"] = False
            if signals["signal"] is not None:
                raise KeyboardInterrupt(f"received signal {signals['signal']}")
            code = process.wait()
            worker_finished = True
            if code:
                raise subprocess.CalledProcessError(code, process.args)
    except (Exception, KeyboardInterrupt) as exc:
        failure = f"{type(exc).__name__}: {exc}; see execution.log; no automatic retries"
    finally:
        # Finalization itself must not release the lock while a worker is alive.
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None and not worker_finished:
                stop_worker(process)
        finally:
            manifest = finalize(root, commit, failure)
    print(f"Study {manifest['status']}: {manifest['completed_condition_runs']}/125 condition runs; {root}")
    return 0 if manifest["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute-lab", action="store_true", help="authorize isolated Docker/OpenPLC study")
    mode.add_argument("--dry-run", "--preflight", action="store_true", help="validate inputs without Docker or capture")
    parser.add_argument("--output", type=Path, help="new evidence directory; existing paths are refused")
    args = parser.parse_args()
    os.chdir(REPO)
    calibration = REPO / "research/v0.6_calibration.json"
    frozen = load_calibration(calibration)
    schedule = plan()
    print(f"Preflight: {len(schedule)} condition runs, 7500 planned transactions, 250 paired detector evaluations")
    print(f"Frozen threshold: {frozen['calibration']['threshold_ms']} ms")
    print("Docker executable:", shutil.which("docker") or "missing (required for execution)")
    for item in schedule:
        print(f"trial-{item['trial']}/{item['condition']}")
    if not args.execute_lab:
        return 0
    if not shutil.which("docker"):
        parser.error("Docker executable is required")
    try:
        with execution_signals() as signals:
            with execution_lock(LOCK_PATH) as lock:
                return execute_lab(args, parser, calibration, schedule, lock, signals)
    except StudyLocked as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
