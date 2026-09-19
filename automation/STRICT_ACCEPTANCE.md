# Strict autonomous acceptance

A task is never complete merely because the model exited successfully.

Tasks 01-04 require:
- substantive implementation changes;
- tests changed;
- collected test count increased;
- full pytest passing;
- package build passing.

Task 05 requires a substantive reproducibility/documentation/script change plus
the same final green repository verification.

Zero-change agent runs are rejected and never receive a `.done` marker.
