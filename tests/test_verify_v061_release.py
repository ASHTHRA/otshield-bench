import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_v061_release.py"
SPEC = importlib.util.spec_from_file_location("verify_v061_release", SCRIPT)
verify = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(verify)


def make_repo(tmp_path: Path) -> Path:
    evidence = tmp_path / "evidence" / "v06" / "20260922T174026Z"
    evidence.mkdir(parents=True)
    research = tmp_path / "research"
    research.mkdir()

    study = {
        "status": "completed",
        "execution_git_commit": verify.EXPECTED_COMMIT,
        "completed_condition_runs": 125,
        "completed_detector_evaluations": 250,
        "failed_attempts": [],
        "unattempted_runs": [],
    }
    (evidence / "study.json").write_text(json.dumps(study), encoding="utf-8")
    for name in verify.REQUIRED_EVIDENCE:
        path = evidence / name
        if not path.exists():
            path.write_text("{}\n", encoding="utf-8")

    (research / "v0.6.1_release_candidate.md").write_text(
        f"""# v0.6.1 Release Candidate

Reference study: `{verify.REFERENCE_STUDY}`

The archived v0.6.0-alpha DOI {verify.ARCHIVED_DOI} predates the newer
post-release study and is not represented as containing it.

No external replication has been completed.
""",
        encoding="utf-8",
    )
    (research / "INDEPENDENT_REPLICATION.md").write_text(
        f"""# Independent Replication

Reference evidence only: `{verify.REFERENCE_STUDY}`

No independent replication has been completed.
""",
        encoding="utf-8",
    )
    (research / "replication_result_template.md").write_text(
        "# Replication Result Template\n\nRecord independent results here.\n",
        encoding="utf-8",
    )
    (research / "VALIDATION_REQUEST.md").write_text(
        "# Validation Request\n\nIndependent replication is requested; no external replication has been completed.\n",
        encoding="utf-8",
    )
    return tmp_path


def study_path(root: Path) -> Path:
    return root / "evidence" / "v06" / "20260922T174026Z" / "study.json"


def load_study(root: Path) -> dict:
    return json.loads(study_path(root).read_text(encoding="utf-8"))


def save_study(root: Path, value: dict) -> None:
    study_path(root).write_text(json.dumps(value), encoding="utf-8")


def test_valid_completed_study_passes(tmp_path):
    root = make_repo(tmp_path)
    assert verify.validate_repo(root) == []


def test_wrong_execution_commit_fails(tmp_path):
    root = make_repo(tmp_path)
    study = load_study(root)
    study["execution_git_commit"] = "deadbeef"
    save_study(root, study)
    errors = verify.validate_repo(root)
    assert any("execution_git_commit" in error for error in errors)


def test_noncompleted_status_fails(tmp_path):
    root = make_repo(tmp_path)
    study = load_study(root)
    study["status"] = "partial"
    save_study(root, study)
    errors = verify.validate_repo(root)
    assert any("status" in error for error in errors)


def test_failed_attempts_fails(tmp_path):
    root = make_repo(tmp_path)
    study = load_study(root)
    study["failed_attempts"] = [{"trial": 1}]
    save_study(root, study)
    errors = verify.validate_repo(root)
    assert any("failed_attempts" in error for error in errors)


def test_missing_aggregate_fails(tmp_path):
    root = make_repo(tmp_path)
    (root / "evidence" / "v06" / "20260922T174026Z" / "aggregate.json").unlink()
    errors = verify.validate_repo(root)
    assert any("aggregate.json" in error for error in errors)


def test_false_old_doi_contains_new_study_claim_fails(tmp_path):
    root = make_repo(tmp_path)
    release = root / "research" / "v0.6.1_release_candidate.md"
    release.write_text(
        f"""# v0.6.1 Release Candidate

Reference study: `{verify.REFERENCE_STUDY}`

The archived DOI {verify.ARCHIVED_DOI} contains the newer post-release
v0.6.1 study.

No external replication has been completed.
""",
        encoding="utf-8",
    )
    errors = verify.validate_repo(root)
    assert any("DOI" in error for error in errors)
