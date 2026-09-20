#!/usr/bin/env python3
"""Fail-closed Jev decision gate for the OTShield agent loop."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from typesafe_sdk import Choice, TypeSafeClient


CRITERIA = {
    "continue": (
        "Continue automated execution because the state is safe and "
        "required prerequisites are available."
    ),
    "retry": (
        "Retry the task automatically when implementation is incomplete, "
        "tests fail, a semantic verification gate rejects the code, a rate "
        "limit is temporary, or another software-level failure can reasonably "
        "be repaired by another bounded coding pass without human intervention."
    ),
    "human_review": (
        "Stop only when human action is actually required, such as invalid "
        "credentials, unavailable external infrastructure, a missing OS-level "
        "prerequisite that automation cannot install, an ambiguous safety "
        "condition, or repeated bounded repair attempts that cannot proceed. "
        "Do not choose human_review merely because code is incomplete, tests "
        "failed, or a semantic verification check rejected an implementation."
    ),
    "finish": (
        "The current task is already complete and no additional "
        "implementation attempt is required."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    if not os.environ.get("TYPESAFE_API_KEY"):
        print(
            "TYPESAFE_API_KEY is missing; Jev gate fails closed.",
            file=sys.stderr,
        )
        return 2

    state = args.state_file.read_text(
        encoding="utf-8",
        errors="replace",
    )

    try:
        client = TypeSafeClient()

        response = client.system_one(
            state=state,
            questions={
                "next_action": Choice(
                    instructions=(
                        "What should the OTShield automation do next?"
                    ),
                    criteria=CRITERIA,
                )
            },
        )

        answer = response.answers["next_action"]
        choice = answer.choice

        if choice not in CRITERIA:
            raise ValueError(
                f"Unexpected Jev decision: {choice!r}"
            )

        result = {
            "choice": choice,
            "confidence": getattr(answer, "confidence", None),
            "probabilities": dict(
                getattr(answer, "probabilities", {}) or {}
            ),
        }

    except Exception as exc:
        print(
            f"Jev gate failed closed: {exc}",
            file=sys.stderr,
        )
        return 3

    if args.json_out:
        args.json_out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(choice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
