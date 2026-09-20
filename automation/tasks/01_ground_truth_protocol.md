Implement deterministic ground-truth derivation from an explicit experiment protocol.

Goal:
- Define a small versioned protocol schema for experiment phases/events.
- Derive expected labels/windows from that protocol without inventing observations.
- Keep synthetic and lab-derived provenance distinct.
- Add tests for valid protocols, malformed input, overlapping windows, and deterministic output.
- Document schema and CLI/API usage.
- Do not require live GRFICS or Docker.
