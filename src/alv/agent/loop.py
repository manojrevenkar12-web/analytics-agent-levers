"""The agent loop: one question in, one outcome out, with every turn's tokens, cost and time accounted.

A planner is a generator. It yields an action (call a tool, ask the person, answer, say it is not sure) and is sent
back what that action returned. The loop runs the tools, relays clarifying questions only when the clarify lever is
on, and stops at the turn limit. It never sees the right answer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class Action:
    kind: str  # tool | ask | answer | abstain
    tool: str = ""
    args: dict = field(default_factory=dict)
    text: str = ""
    sql: str = ""
    rows: list | None = None
    confidence: float = 1.0


@dataclass
class Turn:
    action: Action
    input_tokens: int
    output_tokens: int
    model_seconds: float
    tool_ms: float = 0.0
    error: str | None = None
    observation: object = None


@dataclass
class Outcome:
    qid: str
    kind: str  # answer | abstain | gave_up
    rows: list | None
    sql: str
    confidence: float
    asked: int
    turns: list[Turn]

    @property
    def input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    def usd(self, model: dict) -> float:
        return (self.input_tokens * model["input_usd_per_mtok"] + self.output_tokens * model["output_usd_per_mtok"]) / 1e6

    @property
    def seconds(self) -> float:
        return sum(t.model_seconds + t.tool_ms / 1000 for t in self.turns)


def run(qid: str, question: str, planner, tools, user, levers: set[str], cfg: dict) -> Outcome:
    a, m = cfg["agent"], cfg["model"]
    context_chars = len(question)
    turns: list[Turn] = []
    asked = 0
    gen = planner(question, levers)
    obs: object = None
    for _ in range(a["max_turns"]):
        try:
            act: Action = gen.send(obs) if turns else next(gen)
        except StopIteration:
            break
        out_tok = a["answer_tokens"] if act.kind in ("answer", "abstain") else a["output_tokens_per_turn"]
        in_tok = a["system_prompt_tokens"] + context_chars // a["chars_per_token"]
        turn = Turn(act, in_tok, out_tok, m["seconds_per_turn"] + out_tok / m["output_tokens_per_second"])
        turns.append(turn)
        if act.kind == "answer":
            return Outcome(qid, "answer", act.rows, act.sql, act.confidence, asked, turns)
        if act.kind == "abstain":
            return Outcome(qid, "abstain", None, "", act.confidence, asked, turns)
        if act.kind == "ask":
            if "clarify" not in levers:
                obs = {"error": "asking the person is not enabled; decide yourself"}
            else:
                asked += 1
                obs = {"reply": user(act.text)}
        else:
            c = tools.call(act.tool, act.args)
            turn.tool_ms, turn.error = c.ms, c.error
            obs = {"error": c.error} if c.error else {"result": c.output}
        turn.observation = obs
        context_chars += len(act.text) + len(json.dumps(act.args)) + len(json.dumps(obs, default=str))
    return Outcome(qid, "gave_up", None, "", 0.0, asked, turns)


def timed(fn):
    t = time.perf_counter()
    r = fn()
    return r, (time.perf_counter() - t) * 1000
