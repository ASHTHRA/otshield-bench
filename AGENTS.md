# OTShield Bench Development Instructions

These instructions apply to the entire repository.

## Project purpose

OTShield Bench is a reproducible, vendor-neutral benchmark for measuring OT
cyber-detection effectiveness, deployment and resource cost, and resilience under
degraded connectivity. The benchmark methodology is the principal technical
contribution. Do not turn OTShield into another generic IDS product.

## Scope and safety

- Maintain reproducibility and vendor neutrality.
- Keep v0.x development Modbus-first.
- Run every attack and fault scenario only in an explicitly simulated or authorized
  laboratory environment.
- Preserve the OTB-SCENARIO, OTB-TELEMETRY, OTB-DETECT, and OTB-EVAL abstractions.
- Do not silently change established schemas or interfaces. Document and test any
  intentional compatibility change.
- Defer DNP3 and EtherNet/IP expansion until the Modbus milestone is stable.
- Prefer changes that strengthen eventual open research publication and
  reproducibility.

## Evidence and claims

- Clearly distinguish simulated or synthetic evidence from measurements obtained
  from real research testbeds.
- Do not claim novelty, standards compliance, detection performance, external
  adoption, or real-world validation without reproducible supporting evidence.

## Development workflow

- Include tests with every new feature.
- Run the complete test suite before every commit.
- Never push failing tests.
- Keep commits small, meaningful, chronological, and focused on one coherent change.
- Do not squash development history unless explicitly requested.
- Use SSH for this repository and preserve the existing dedicated deploy-key
  configuration.
- Keep generated artifacts, temporary files, credentials, keys, and secrets out of
  Git.
- Never commit real credentials or private SSH material.
