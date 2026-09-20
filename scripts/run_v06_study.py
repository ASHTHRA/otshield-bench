#!/usr/bin/env python3
"""Preflight by default; --execute-lab explicitly starts the isolated 25-trial lab."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import signal
import subprocess

from otshield.paired_v06 import load_calibration
from otshield.study_v06 import finalize, plan, write_json

REPO = Path(__file__).resolve().parents[1]


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
    shutil.copyfile(calibration, root / "calibration.json")
    shutil.copyfile(REPO / "research/v0.6_experiment_protocol.md", root / "experiment_protocol.md")
    write_json(root / "execution.json", {"execution_git_commit": commit, "schedule": schedule})
    failure = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with (root / "execution.log").open("w") as log:
            process = subprocess.Popen(["bash", "scripts/run_v06_lab_worker.sh"],
                           env={**os.environ, "V06_LAB_AUTHORIZED": "1", "V06_ROOT": str(root), "V06_STAMP": stamp},
                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait()
                if code:
                    raise subprocess.CalledProcessError(code, process.args)
            except KeyboardInterrupt:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
    except (subprocess.SubprocessError, OSError, KeyboardInterrupt) as exc:
        failure = f"{type(exc).__name__}: {exc}; see execution.log; no automatic retries"
    finally:
        manifest = finalize(root, commit, failure)
    print(f"Study {manifest['status']}: {manifest['completed_condition_runs']}/125 condition runs; {root}")
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
