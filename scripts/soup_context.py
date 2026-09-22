"""Offline, optional task context. Permanent policy never passes through Soup."""
from __future__ import annotations

import sys

CONTEXTS = (
    ("modbus-pcap", "Modbus PCAP transaction correlation retransmission ingestion",
     "Correlate Modbus transactions per connection; test duplicates and unmatched frames."),
    ("simulation", "simulation Docker Compose preflight adapter GRFICS OpenPLC",
     "Use mocked prerequisite checks for adapter tests; distinguish configuration from execution."),
    ("results", "results manifest reproducibility provenance evaluation ground truth",
     "Preserve schema versions, seeds, configuration and provenance in result manifests."),
)


def route(task: str) -> str:
    from soup import Soup

    router = Soup()
    for name, description, instructions in CONTEXTS:
        router.register(name=name, description=description, instructions=instructions)
    result = router.prepare(task)
    if not isinstance(result, str) or len(result) > 32000:
        raise ValueError("Invalid routing output")
    return result


if __name__ == "__main__":
    try:
        print(route(sys.stdin.read()))
    except Exception:
        # Provider/library exceptions must never disclose environment values.
        print("Soup routing unavailable", file=sys.stderr)
        raise SystemExit(2)
