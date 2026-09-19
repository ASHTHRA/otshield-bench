Create a versioned benchmark result manifest and report generator.

Goal:
- Capture benchmark version, detector adapter, protocol, seed, provenance, environment metadata, effectiveness metrics, measured resource-cost metrics, and degraded-connectivity settings.
- Generate a concise Markdown summary.
- Validate missing/invalid fields.
- Add deterministic tests and synthetic examples clearly labeled synthetic.
- Never populate unmeasured values with invented numbers.
