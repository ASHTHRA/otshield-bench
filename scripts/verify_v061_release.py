#!/usr/bin/env python3
"""Read-only validation gate for the OTShield Bench v0.6.1-alpha release candidate."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

REFERENCE_STUDY = "evidence/v06/20260922T174026Z/"
EXPECTED_COMMIT = "88e1f056dc2143129ef115f3ce1ad731fd0e9a0e"
ARCHIVED_DOI = "10.5281/zenodo.22899466"

REQUIRED_EVIDENCE = (
    "study.json",
    "aggregate.json",
    "calibration.json",
    "execution.json",
    "experiment_protocol.md",
    "STUDY_SHA256SUMS",
)

REQUIRED_DOCS = (
    "research/v0.6.1_release_candidate.md",
    "research/INDEPENDENT_REPLICATION.md",
    "research/replication_result_template.md",
    "research/VALIDATION_REQUEST.md",
)


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path}: {exc}")
        return ""


def _load_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path} must contain a JSON object")
        return {}
    return value


def _positive_replication_claim(text: str) -> bool:
    success_words = re.compile(
        r"\b(completed|confirmed|validated|verified|successful|replicated|reproduced)\b",
        re.IGNORECASE,
    )
    negation = re.compile(
        r"\b(no|not|never|without|pending|planned|requested|requesting|"
        r"has not|have not|hasn't|haven't|not yet|yet to)\b",
        re.IGNORECASE,
    )
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        low = sentence.lower()
        if ("external replication" in low or "independent replication" in low) and success_words.search(sentence):
            if not negation.search(sentence):
                return True
    return False


def _old_doi_false_claim(text: str) -> bool:
    patterns = (
        rf"{re.escape(ARCHIVED_DOI)}.{{0,180}}\b(contains|includes|incorporates|covers|archives)\b.{{0,180}}(20260922T174026Z|v0\.6\.1|newer|post-release)",
        rf"\b(contains|includes|incorporates|covers|archives)\b.{{0,180}}(20260922T174026Z|v0\.6\.1|newer|post-release).{{0,180}}{re.escape(ARCHIVED_DOI)}",
    )
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def validate_repo(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    evidence_dir = root / REFERENCE_STUDY.rstrip("/")

    for name in REQUIRED_EVIDENCE:
        if not (evidence_dir / name).is_file():
            errors.append(f"missing required evidence file: {REFERENCE_STUDY}{name}")

    docs: dict[str, str] = {}
    for rel in REQUIRED_DOCS:
        path = root / rel
        if not path.is_file():
            errors.append(f"missing required research document: {rel}")
        else:
            docs[rel] = _read_text(path, errors)

    study_path = evidence_dir / "study.json"
    if study_path.is_file():
        study = _load_json(study_path, errors)
        expected = {
            "status": "completed",
            "execution_git_commit": EXPECTED_COMMIT,
            "completed_condition_runs": 125,
            "completed_detector_evaluations": 250,
            "failed_attempts": [],
            "unattempted_runs": [],
        }
        for key, wanted in expected.items():
            got = study.get(key)
            if got != wanted:
                errors.append(f"study.json {key}: expected {wanted!r}, got {got!r}")

    release = docs.get("research/v0.6.1_release_candidate.md", "")
    replication = docs.get("research/INDEPENDENT_REPLICATION.md", "")

    if release and REFERENCE_STUDY not in release:
        errors.append("release candidate does not reference the post-release study path")
    if replication and REFERENCE_STUDY not in replication:
        errors.append("independent replication guide does not identify the reference study path")

    if release:
        if ARCHIVED_DOI not in release:
            errors.append("release candidate does not identify the archived v0.6.0-alpha DOI")
        boundary_terms = ("predates", "does not contain", "does not include", "not represented as")
        if not any(term in release.lower() for term in boundary_terms):
            errors.append("release candidate does not clearly preserve the old-DOI/new-study boundary")

    joined_docs = "\n".join(docs.values())
    if joined_docs and _old_doi_false_claim(joined_docs):
        errors.append("documentation falsely represents the archived v0.6.0-alpha DOI as containing the newer study")
    if joined_docs and _positive_replication_claim(joined_docs):
        errors.append("documentation claims successful external/independent replication that has not occurred")

    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_root,
        help="repository root to validate (default: repository containing this script)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    errors = validate_repo(args.repo_root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: v0.6.1 release validation failed with {len(errors)} issue(s)")
        return 1

    print("PASS: required evidence files present")
    print("PASS: study manifest matches completed 125-run / 250-evaluation reference")
    print("PASS: release and replication documents reference the post-release study")
    print("PASS: archived DOI boundary preserved; no completed external replication claimed")
    print("PASS: v0.6.1 release validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
