"""MCP over stdio, the Claude planner against a scripted API, and Langfuse traces."""

from __future__ import annotations

import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import httpx

from alv.agent.claude import ClaudePlanner
from alv.agent.loop import run
from alv.mcp_server import handle
from alv.tools import Tools
from alv.trace import events, send

from helpers import cfg, session


def test_mcp_handles_the_protocol():
    t = Tools(session(), cfg(), metric_catalog=True)
    lv = {"metric_catalog"}
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, t, lv)
    assert init["result"]["capabilities"] == {"tools": {}}
    names = [x["name"] for x in handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, t, lv)["result"]["tools"]]
    assert names == ["list_tables", "describe_table", "run_select_query", "get_metric"]
    r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "run_select_query",
                "arguments": {"query": "SELECT count() FROM analytics.dim_plans"}}}, t, lv)["result"]
    assert not r["isError"] and json.loads(r["content"][0]["text"])["rows"] == [[4]]
    bad = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "run_select_query",
                  "arguments": {"query": "DROP TABLE analytics.dim_plans"}}}, t, lv)["result"]
    assert bad["isError"]
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, t, lv) is None
    assert handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_metric"}}, t, set())["error"]


def test_mcp_server_runs_over_stdio():
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_metric", "arguments": {"term": "revenue"}}}]
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "alv-ch-*")))
    p = subprocess.run([sys.executable, "-m", "alv.mcp_server"], input="\n".join(map(json.dumps, msgs)) + "\n",
                       capture_output=True, text=True, timeout=120)
    for d in set(glob.glob(os.path.join(tempfile.gettempdir(), "alv-ch-*"))) - before:  # the server's private warehouse
        shutil.rmtree(d, ignore_errors=True)
    replies = [json.loads(x) for x in p.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2]
    assert json.loads(replies[1]["result"]["content"][0]["text"])["table"] == "mart_revenue_daily"


def scripted_api(turns):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        calls.append(body)
        return httpx.Response(200, json={"content": turns[len(calls) - 1]})
    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_claude_planner_explores_and_answers():
    http, calls = scripted_api([
        [{"type": "tool_use", "id": "a", "name": "get_metric", "input": {"term": "revenue"}}],
        [{"type": "tool_use", "id": "b", "name": "final_answer",
          "input": {"sql": "SELECT count() FROM analytics.dim_plans", "confidence": 0.9}}],
    ])
    c = cfg()
    o = run("q", "How many plans?", ClaudePlanner(http=http, api_key="k"), Tools(session(), c, metric_catalog=True),
            lambda t: "", {"metric_catalog"}, c)
    assert o.kind == "answer" and o.rows == [[4]] and o.confidence == 0.9
    assert {t["name"] for t in calls[0]["tools"]} >= {"get_metric", "final_answer"}
    assert calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_claude_planner_can_say_not_sure_only_with_the_lever():
    http, calls = scripted_api([[{"type": "tool_use", "id": "a", "name": "not_sure", "input": {"reason": "no data"}}]])
    c = cfg()
    o = run("q", "NPS?", ClaudePlanner(http=http, api_key="k"), Tools(session(), c), lambda t: "", {"abstain"}, c)
    assert o.kind == "abstain"
    assert "not_sure" not in {t["name"] for t in ClaudePlanner(http=http).tools(set())}


def test_traces_are_langfuse_ingestion_events():
    c = cfg()
    http, _ = scripted_api([[{"type": "tool_use", "id": "b", "name": "final_answer",
                              "input": {"sql": "SELECT 1", "confidence": 1}}]])
    o = run("q7", "One?", ClaudePlanner(http=http, api_key="k"), Tools(session(), c), lambda t: "", set(), c)
    ev = events("run1", "One?", o, c["model"], "baseline", "correct")
    types = [e["type"] for e in ev]
    assert types[0] == "trace-create" and types[-1] == "score-create" and "generation-create" in types
    gen = next(e for e in ev if e["type"] == "generation-create")["body"]
    assert gen["usage"]["unit"] == "TOKENS" and gen["traceId"] == ev[0]["body"]["id"]
    assert ev == events("run1", "One?", o, c["model"], "baseline", "correct")  # ids are stable: replay is idempotent
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        seen["n"] = len(json.loads(req.content)["batch"])
        return httpx.Response(207, json={"successes": [], "errors": []})
    send(ev, "https://lf.example", "pk", "sk", httpx.Client(transport=httpx.MockTransport(handler)))
    assert seen["auth"] == "Basic " + base64.b64encode(b"pk:sk").decode() and seen["n"] == len(ev)
