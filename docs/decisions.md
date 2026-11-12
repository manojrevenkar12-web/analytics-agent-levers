# Decisions

## A stand-in for the model, a real database

There is no model API key in this environment, so the agent's choices come from a seeded policy
(`src/alv/sim/planner.py`) that does what an LLM agent does with what it can see: it reads the question, explores the
schema through the same MCP tools, picks tables and columns by the words in names and descriptions, and guesses where
nothing tells it. Its mistakes are the documented ones: look-alike tables, the wrong amount column, a forgotten status
filter, the first of several matching accounts. Its noise settings are in `config/world.toml [model]` and no lever
changes them; a lever only changes what the tools return or what the agent may do.

Everything else is real: the warehouse is ClickHouse (chDB, embedded), every query the agent writes runs against it,
answers are judged on result sets, and the tools are the ones an MCP client would get.

`src/alv/agent/claude.py` is the same planner interface on the Anthropic Messages API with tool use, tested against a
scripted API. Measuring a real model is one constructor away; it is not done here.

## Same luck for every setting

Each random choice of the stand-in is drawn from a hash of (seed, question, decision). Two lever settings facing the
same question get the same draws, so differences come from the lever, and intervals are paired per question.

## Judged on result sets

Two different SQL statements can both be right (net revenue from the mart, or from paid invoices' net amounts). The
scorer compares rows with a 0.5% tolerance, the way the person reading the answer would.

## What counts as right

A clarifying question to an ambiguous request is right if the answer after it is right. "Not sure" to a question about
data the warehouse does not hold is right. "Not sure" to an answerable question is a miss, not an error: the gate
treats confidently wrong answers as the cost that matters and tracks misses separately.

## The gate includes friction

An agent that asks a clarifying question in most conversations is right more often and used less. The gate holds a
setting that asks more than 40 times per 100 questions, whatever its accuracy.

## Traces in Langfuse's format

Runs are written as Langfuse ingestion events: a trace per question, a generation per model turn with token usage and
cost, a span per tool call, and the verdict as a score. IDs are derived from the run and the question, so replaying a
batch does not duplicate traces.
