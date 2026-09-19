# OTShield autonomous development loop

This loop processes the task queue using Codex in workspace-write sandbox mode.

Safety:
- never runs automated work on main;
- tests and builds current v0.3 before agent work;
- first task audits research/documentation claims;
- verifies full tests/build after every task;
- rolls back failed iterations;
- commits/pushes only the automation branch;
- never automatically merges to main.
