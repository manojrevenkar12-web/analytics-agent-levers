# Repeatable tasks

## Try a new lever

1. Name it in `config/platform.toml [levers] order` and `[levers.labels]`.
2. Make it change what a tool returns (`src/alv/tools.py`) or what the agent may do (`src/alv/agent/loop.py`), and teach
   the stand-in to use it the way a model would (`src/alv/sim/planner.py`), without touching `[model]`.
3. `pytest -q && python scripts/evaluate.py && python scripts/report.py`: it gets a row, a gate decision and a marginal value.

## Measure a real model

Construct `ClaudePlanner(model=..., api_key=...)` and pass it where `evaluate_seed` builds the stand-in. Prices go in
`config/platform.toml [model]`.

## Send traces to Langfuse

`LANGFUSE_HOST=... LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... python scripts/traces.py --send`

## Serve the tools to an MCP client

`python -m alv.mcp_server --levers descriptions,metric_catalog` (stdio).
