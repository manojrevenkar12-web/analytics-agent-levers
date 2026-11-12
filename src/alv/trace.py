"""Every agent run as a Langfuse trace: a trace per question, a generation per model turn with token usage and cost,
a span per tool call with its input and output, and the eval verdict as a score. The events are the batch format of
Langfuse's public ingestion API, so the same run can be replayed into a Langfuse project.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx

BASE = datetime(2026, 11, 1, tzinfo=UTC)


def _id(*parts) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(map(str, parts))))


def _ts(seconds: float) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def events(run_id: str, question: str, outcome, model: dict, setting: str, verdict: str | None = None, start: float = 0.0
           ) -> list[dict]:
    tid = _id(run_id, outcome.qid)
    clock = start
    out = []
    for i, t in enumerate(outcome.turns):
        gen_end = clock + t.model_seconds
        out.append({"id": _id(tid, "g", i), "timestamp": _ts(clock), "type": "generation-create", "body": {
            "id": _id(tid, "gen", i), "traceId": tid, "name": f"turn {i + 1}: {t.action.kind}", "model": model["name"],
            "startTime": _ts(clock), "endTime": _ts(gen_end),
            "usage": {"input": t.input_tokens, "output": t.output_tokens, "unit": "TOKENS"},
            "costDetails": {"input": t.input_tokens * model["input_usd_per_mtok"] / 1e6,
                            "output": t.output_tokens * model["output_usd_per_mtok"] / 1e6},
            "output": {"action": t.action.kind, "tool": t.action.tool, "args": t.action.args, "text": t.action.text}}})
        clock = gen_end
        if t.action.kind in ("tool", "ask"):
            end = clock + t.tool_ms / 1000
            out.append({"id": _id(tid, "s", i), "timestamp": _ts(clock), "type": "span-create", "body": {
                "id": _id(tid, "span", i), "traceId": tid, "name": t.action.tool or "ask_user",
                "startTime": _ts(clock), "endTime": _ts(end), "input": t.action.args or {"text": t.action.text},
                "output": json.loads(json.dumps(t.observation, default=str)[:20000]) if t.observation is not None
                and len(json.dumps(t.observation, default=str)) <= 20000 else {"truncated": True},
                "level": "ERROR" if t.error else "DEFAULT", "statusMessage": t.error}})
            clock = end
    out.insert(0, {"id": _id(tid, "t"), "timestamp": _ts(start), "type": "trace-create", "body": {
        "id": tid, "name": "analytics-question", "input": question, "timestamp": _ts(start),
        "output": {"kind": outcome.kind, "rows": (outcome.rows or [])[:20], "sql": outcome.sql},
        "metadata": {"setting": setting, "confidence": round(outcome.confidence, 4), "asked": outcome.asked},
        "tags": [setting]}})
    if verdict is not None:
        out.append({"id": _id(tid, "score"), "timestamp": _ts(clock), "type": "score-create", "body": {
            "id": _id(tid, "verdict"), "traceId": tid, "name": "correct", "value": 1 if verdict == "correct" else 0,
            "dataType": "NUMERIC", "comment": verdict}})
    return out


def send(batch: list[dict], host: str | None = None, public: str | None = None, secret: str | None = None,
         http: httpx.Client | None = None) -> dict:
    """POST to Langfuse's ingestion API. Keys come from LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."""
    host = host or os.environ["LANGFUSE_HOST"]
    auth = base64.b64encode(f"{public or os.environ['LANGFUSE_PUBLIC_KEY']}:{secret or os.environ['LANGFUSE_SECRET_KEY']}"
                            .encode()).decode()
    client = http or httpx.Client(timeout=30)
    r = client.post(f"{host.rstrip('/')}/api/public/ingestion", json={"batch": batch},
                    headers={"Authorization": f"Basic {auth}"})
    r.raise_for_status()
    return r.json()
