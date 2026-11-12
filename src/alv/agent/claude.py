"""The same planner interface backed by a real model through the Anthropic Messages API with tool use.

Not run in this repository's evaluation (no API key here); tested against a scripted API. To measure a real model,
pass `ClaudePlanner(...)` where the evaluation passes the stand-in.
"""

from __future__ import annotations

import json
import os

import httpx

from alv.agent.loop import Action
from alv.tools import tool_specs

SYSTEM = """You answer business questions from a ClickHouse warehouse. Explore with the tools, then call final_answer
with one SELECT that answers the question and your confidence from 0 to 1. Use get_metric for business terms when it
is available. {extra}"""

CONTROL = {
    "final_answer": {"type": "object", "properties": {"sql": {"type": "string"}, "confidence": {"type": "number"}},
                     "required": ["sql", "confidence"]},
    "ask_user": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    "not_sure": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
}


class ClaudePlanner:
    def __init__(self, model: str = "claude-sonnet-4-5", http: httpx.Client | None = None, max_tokens: int = 1024,
                 base_url: str | None = None, api_key: str | None = None) -> None:
        self.model = model
        self.http = http or httpx.Client(timeout=60)
        self.max_tokens = max_tokens
        self.base = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
        self.key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def tools(self, levers: set[str]) -> list[dict]:
        specs = tool_specs(levers) + [{"name": "final_answer", "description": "Give the answer as one SELECT.",
                                       "input_schema": CONTROL["final_answer"]}]
        if "clarify" in levers:
            specs.append({"name": "ask_user", "description": "Ask the person one short question when a term or name is ambiguous.",
                          "input_schema": CONTROL["ask_user"]})
        if "abstain" in levers:
            specs.append({"name": "not_sure", "description": "Say you cannot answer reliably.", "input_schema": CONTROL["not_sure"]})
        return specs

    def _call(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        r = self.http.post(f"{self.base}/v1/messages", json={"model": self.model, "max_tokens": self.max_tokens,
                           "system": system, "tools": tools, "messages": messages},
                           headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        return r.json()

    def __call__(self, question: str, levers: set[str]):
        extra = "Say not_sure rather than guess." if "abstain" in levers else ""
        system = SYSTEM.format(extra=extra)
        tools = self.tools(levers)
        messages: list[dict] = [{"role": "user", "content": question}]
        while True:
            resp = self._call(system, messages, tools)
            messages.append({"role": "assistant", "content": resp["content"]})
            uses = [b for b in resp["content"] if b.get("type") == "tool_use"]
            if not uses:
                yield Action("abstain", text="The model stopped without an answer.", confidence=0.0)
                return
            use = uses[0]
            name, args = use["name"], use.get("input") or {}
            if name == "final_answer":
                obs = yield Action("tool", tool="run_select_query", args={"query": args["sql"]})
                if obs.get("error"):
                    result = {"error": obs["error"]}
                else:
                    yield Action("answer", rows=obs["result"]["rows"], sql=args["sql"], confidence=float(args["confidence"]))
                    return
            elif name == "not_sure":
                yield Action("abstain", text=args.get("reason", ""), confidence=0.0)
                return
            elif name == "ask_user":
                result = yield Action("ask", text=args["question"])
            else:
                result = yield Action("tool", tool=name, args=args)
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": use["id"],
                                                          "content": json.dumps(result, default=str)[:20000],
                                                          "is_error": "error" in result}]})
