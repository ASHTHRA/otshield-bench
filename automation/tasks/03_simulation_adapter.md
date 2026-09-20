Harden the simulation-container adapter without pretending a full GRFICSv3 lab exists.

Goal:
- Provide a deterministic interface/config for launching or attaching to a simulation when Docker is available.
- Add preflight checks for Docker/Compose/network prerequisites.
- Fail closed with clear diagnostics when macvlan/NIC/RAM prerequisites are absent.
- Add unit tests using mocks only.
- Keep real lab execution as an explicit external milestone.
