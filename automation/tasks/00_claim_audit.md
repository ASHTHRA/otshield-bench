Audit all v0.3 documentation and code comments for claims that exceed repository evidence.

Specifically:
- distinguish implemented code from runtime-validated experiments;
- ensure no text says a GRFICS/OpenPLC lab, real capture, Docker experiment, or benchmark measurement succeeded unless an artifact proves it;
- avoid describing network packet timing as fully deterministic merely because polling/configuration is seeded;
- verify README command paths against the actual repository layout;
- keep current blockers explicit;
- add/update tests only if needed to prevent misleading examples.
Make the smallest truthful documentation fixes required.
