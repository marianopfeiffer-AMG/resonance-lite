# Schemas

The canonical JSON Schemas ship inside the CLI package so `rlite` can load them at runtime:

- [`plan.v1.json`](../cli/src/rl/schemas/plan.v1.json): the plan Claude writes for each job.

State files (`state/*.json`) are written only by `rlite` and validated in code.
