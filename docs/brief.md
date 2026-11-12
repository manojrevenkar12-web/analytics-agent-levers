# Product brief: making a data agent trustworthy enough to ask again

## The problem

An agent answering business questions from a warehouse fails in a way people notice once: it answers confidently and
wrongly. ClickHouse's own benchmark of analytics agents found that "discovering relevant tables is often more difficult
than writing executable SQL, and incorrect planning accounts for most failures" ([ClickHouse, The Agentic Analytics
Benchmark](https://clickhouse.com/blog/agentic-analytics-benchmark-data-agent-mnist)). A better model helps; this brief
is about what the *product* can change around any model.

## Who it is for

- **The person asking** (finance, sales ops, a team lead): wants the number they would get from the data team, or to be
  told the agent is not sure. A wrong number costs more than no number.
- **The data team that owns the warehouse**: wants to know which of its work (descriptions, a metric catalogue)
  actually moves answer quality, and in what order to do it.
- **The platform** (ClickHouse Agents, the Agentic Data Stack): wants answers that are right, cheap per question, and
  measured in Langfuse rather than guessed.

## What was measured

Four levers a product team can ship, on the same 720 questions with the same luck (results in the README):

| Lever | What ships |
|---|---|
| Table and column descriptions | Descriptions as ClickHouse COMMENTs, visible to every MCP client |
| Verified metric catalogue | A `get_metric` tool that returns the data team's definition of a business term |
| Ask when ambiguous | The agent may ask one clarifying question |
| Say "not sure" | The agent declines below a confidence floor |

## What the numbers say

1. **Descriptions first.** They are the largest single lever and still the largest on top of everything else. They
   are also the cheapest to ship: generate drafts from the schema and query history, and let the data team correct
   them.
2. **"Not sure" only after descriptions.** On its own it declines two questions in three, because without context the
   agent is rarely confident. On top of the other levers it removes most of the remaining confidently wrong answers.
   Shipping it first would look like a broken product.
3. **Clarifying questions need a budget.** On its own the agent asks in most questions; with descriptions and the
   catalogue it asks in about a quarter. The gate holds any setting that asks more than 40 times in 100.
4. **The catalogue is worth less than its reputation once descriptions exist**, and it is brittle: in the held-out
   company, people said "turnover" and "engaged customers", which no catalogue term matched.
5. **Right answers get cheaper.** Cost per question barely moves, but cost per *correct* answer falls by about two
   thirds, because fewer questions are wasted. That is the number to price on.

## The loop that keeps it working

In the held-out company, one question in five got "not sure", most often on company-defined words, including two
nobody had defined. Those
"not sure" traces are the data team's to-do list. In Langfuse, filter traces with the verdict score at zero and an
abstain output, group by the term the agent could not resolve, and add the top terms as catalogue synonyms or
description text. The repository writes its runs as Langfuse ingestion events for exactly this.

## Pricing

Price per answered question, not per token: the customer cares about answers, and the levers lower our cost per correct
answer far more than they lower cost per question. A per-question price with a monthly included volume keeps the
margin when a customer's warehouse is poorly described (more turns, more tokens) and rewards the work that makes it
better. Model prices are in `config/platform.toml`; swapping the model re-prices every table.

## Launch plan

1. Descriptions: generated drafts plus a review screen for the data team; measure with the gate on the customer's own
   questions (the harness runs against any warehouse with the same tools).
2. "Not sure" with the floor from config, on for workspaces whose descriptions cover their most-queried tables.
3. Clarifying questions with a per-conversation limit.
4. Catalogue for the ten metrics finance reports, with synonyms mined from "not sure" traces.

Success: share of questions answered correctly, confidently wrong answers per 1,000, cost per correct answer, and
questions asked per 100, all per workspace in Langfuse.

## What this does not show

The agent's choices come from a stand-in policy, not a language model (see `docs/decisions.md`). The levers'
*direction* and *ordering* follow from what each lever lets the agent see; the exact percentages would differ with a
real model and should be re-measured with `ClaudePlanner` on real questions before any launch decision.
