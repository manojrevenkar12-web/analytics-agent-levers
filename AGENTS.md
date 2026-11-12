# Working in this repository

## Fast feedback

- `pytest -q` (about 10 s) and `ruff check .` before every commit; `cd web && npm test` for the dashboard.
- `python scripts/evaluate.py` (about 40 s) runs every lever setting on the tuning questions.

## Invariants

- **Nothing that answers reads the truth.** `src/alv/agent`, `src/alv/tools.py` and `src/alv/mcp_server.py` see the
  question and what ClickHouse returns. `src/alv/world`, `src/alv/sim/user.py`, `src/alv/evals` and `scripts/` may
  read the truth. The stand-in planner reads only the question and tool results (`test_the_stand_in_never_reads_the_truth`).
- **Levers change what the agent can see or do, never its skill.** The stand-in's noise lives in `config/world.toml
  [model]`; no lever touches it.
- **Same luck for every setting.** Random draws are keyed by (seed, question, decision).
- **Read-only tools.** Only SELECT reaches ClickHouse from the agent.
- **Settings in config.** Prices, levers, the gate and metric definitions are in `config/platform.toml`; descriptions
  in `config/descriptions.toml`.
- **Reports are generated.** `reports/*.json`, `web/public/data.json` and the README results come from scripts.

## The held-out rule

`config/world_heldout.toml` runs once through `scripts/heldout.py` after `--lock`. A test fails if settings or code
change after the run; a change needs a new held-out company, not a re-run.
