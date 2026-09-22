"""Bounded development in disposable clones; never reset or publish the source repo."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = """The harness owns task state. Do not create done/blocked markers, commit,
push, merge, tag or release. Do not alter scientific results to satisfy tests.
Work only on this task; include tests. Run scenarios only in explicitly simulated
or authorized laboratories. Never expose or persist API keys. Never fabricate
GRFICS/OpenPLC/PCAP execution or benchmark evidence. Use python -m pytest.
"""


def environment(root: Path, *, credentials: tuple[str, ...] = ()) -> dict[str, str]:
    # Only explicitly needed credentials reach each subprocess.
    env = {k: v for k, v in os.environ.items()
           if not any(word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    for key in credentials:
        if key in os.environ:
            env[key] = os.environ[key]
    env["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def run(args: list[str], root: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=root, env=environment(root), text=True,
                          capture_output=True, timeout=kwargs.pop("timeout", 600), **kwargs)


def pending(root: Path, only: str = "") -> list[Path]:
    return [p for p in sorted((root / "automation/tasks").glob("[0-9][0-9]_*.md"))
            if (not only or p.name == only)
            and not Path(str(p) + ".done").exists()
            and not Path(str(p) + ".blocked").exists()]


def prompt(root: Path, task: Path, soup_python: str | None = None) -> str:
    task_text = task.read_text()
    context = ""
    if soup_python:
        try:
            result = run([soup_python, str(ROOT / "scripts/soup_context.py")],
                         root, input=task_text, timeout=30)
            if result.returncode == 0 and len(result.stdout) <= 32000:
                context = result.stdout
        except (OSError, subprocess.TimeoutExpired):
            pass
        if not context:
            print("Soup unavailable; using task and permanent guardrails only.")
    return "\n\n".join(((root / "AGENTS.md").read_text(),
                            (root / "automation/AGENT_GUARDRAILS.md").read_text(),
                            POLICY, "OPTIONAL TASK CONTEXT:\n" + context,
                            "TASK:\n" + task_text))


def verify(root: Path) -> bool:
    for command in ([sys.executable, "-m", "pytest", "-q"],
                    [sys.executable, "-m", "build"]):
        if run(command, root).returncode:
            return False
    return True


def jev(root: Path, task: Path) -> str:
    # Send bounded task context, never raw provider output or environment.
    with tempfile.TemporaryDirectory(prefix="otshield-jev-") as temporary:
        state = Path(temporary) / "state.txt"
        state.write_text("A bounded implementation attempt failed verification.\n" + task.read_text())
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/jev_gate.py"), "--state-file", str(state)],
                cwd=root, env=environment(root, credentials=("TYPESAFE_API_KEY",)),
                text=True, capture_output=True, timeout=120)
            choice = result.stdout.strip()
            return choice if result.returncode == 0 and choice in {"retry", "continue"} else "human_review"
        except (OSError, subprocess.TimeoutExpired):
            return "human_review"


def implement(root: Path, text: str, model: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="otshield-aider-") as temporary:
        path = Path(temporary)
        message = path / "prompt.txt"
        message.write_text(text)
        try:
            result = subprocess.run([
                "aider", "--model", model, "--model-settings-file",
                str(ROOT / "automation/aider-groq-settings.yml"),
                "--message-file", str(message), "--yes-always", "--no-auto-commits",
                "--no-dirty-commits", "--no-auto-lint", "--no-auto-test",
                "--no-check-update", "--no-show-release-notes", "--no-stream",
                "--no-gitignore", "--chat-history-file", os.devnull,
                "--input-history-file", os.devnull],
                cwd=root, env=environment(root, credentials=("GROQ_API_KEY",)),
                capture_output=True, text=True, timeout=720)
            # Do not print/store provider output: it can contain credentials.
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-task", default=os.environ.get("ONLY_TASK", ""))
    parser.add_argument("--smoke", action="store_true", help="Route synthetic context without running agents")
    args = parser.parse_args()
    soup_python = os.environ.get("SOUP_PYTHON")
    if not soup_python and (ROOT / ".soup-venv/bin/python").exists():
        soup_python = str(ROOT / ".soup-venv/bin/python")
    if args.smoke:
        if not soup_python:
            raise RuntimeError("Set SOUP_PYTHON to an interpreter with soup-ai==0.2.1")
        result = run([soup_python, str(ROOT / "scripts/soup_context.py")], ROOT,
                     input="simulation Docker Compose preflight adapter", timeout=30)
        if result.returncode or "mocked prerequisite" not in result.stdout:
            raise RuntimeError("Soup smoke failed")
        print("Soup offline routing smoke passed; no task executed.")
        return 0
    tasks = pending(ROOT, args.only_task)
    if not tasks:
        print("No pending tasks; completed and blocked tasks were skipped.")
        return 0
    if run(["git", "status", "--porcelain"], ROOT).stdout.strip():
        raise RuntimeError("Commit or set aside local changes before starting a candidate")
    if not shutil.which("aider") or not all(os.environ.get(k) for k in ("GROQ_API_KEY", "TYPESAFE_API_KEY")):
        raise RuntimeError("Aider, GROQ_API_KEY and TYPESAFE_API_KEY are required")
    if not verify(ROOT):
        raise RuntimeError("Baseline verification failed")
    # One candidate per invocation: review it before processing dependent tasks.
    task = tasks[0]
    runtime = ROOT / ".otshield-runtime"
    runtime.mkdir(exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix="candidate-", dir=runtime))
    run(["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(candidate)], ROOT, check=True)
    print(f"Candidate workspace: {candidate}")
    candidate_task = candidate / task.relative_to(ROOT)
    text = prompt(ROOT, task, soup_python)
    for attempt, model in enumerate(("groq/openai/gpt-oss-20b", "groq/openai/gpt-oss-120b")):
        if implement(candidate, text, model) and verify(candidate):
            print("Candidate passed tests/build; human review required. No completion marker written.")
            return 0
        if attempt == 0 and jev(candidate, candidate_task) in {"retry", "continue"}:
            text += "\nRepair the existing candidate. Run python -m pytest -q and resolve failures."
            continue
        break
    print("Candidate requires human review; source repository and task markers preserved.")
    return 20


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError):
        print("Runner stopped safely; check prerequisites and candidate workspace.", file=sys.stderr)
        raise SystemExit(2)
