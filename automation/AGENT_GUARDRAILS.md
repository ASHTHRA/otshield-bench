# OTShield Bench autonomous-agent guardrails

You are developing an open, reproducible OT/ICS cybersecurity benchmark.

Non-negotiable rules:
1. Never fabricate measurements, packet captures, detector results, GRFICS execution, Docker execution, hardware availability, CI outcomes, publications, users, or adoption.
2. Synthetic fixtures must be explicitly identified as synthetic. Lab-derived data must include provenance.
3. Do not claim GRFICSv3/OpenPLC runtime validation unless the environment actually ran it and produced verifiable artifacts.
4. Do not call code "deterministic" when wall-clock timing, Docker scheduling, packet timing, or network behavior can vary; distinguish deterministic data generation from runtime timing.
5. Do not weaken/delete tests merely to get a green run.
6. Never commit secrets, credentials, tokens, .env files, raw sensitive captures, build artifacts, or virtual environments.
7. The outer harness owns commits, pushes, tags, merges, and releases.
8. Preserve backward compatibility unless a task explicitly requires a versioned breaking change.
9. Favor deterministic offline tests and small dependencies.
10. Every implemented capability needs tests and concise documentation.
11. When blocked by Docker, NIC/macvlan, RAM, hardware, or external services, implement only safe offline scaffolding/tests and document the blocker truthfully.
12. Keep tooling defensive/benchmark-oriented: no exploit automation, credential theft, persistence, evasion, destructive control logic, or active attack execution.
13. Record seed/version/config/provenance where applicable.
14. Audit documentation against actual repository evidence before making research claims.
