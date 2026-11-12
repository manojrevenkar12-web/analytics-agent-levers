"""The agent's tools as an MCP server over stdio (JSON-RPC 2.0, one message per line), so LibreChat, Claude Desktop or
any MCP client can use the same tools, descriptions and metric catalogue the evaluation measures.

    python -m alv.mcp_server --levers descriptions,metric_catalog
"""

from __future__ import annotations

import argparse
import json
import sys

from alv.config import platform, world
from alv.tools import Tools, set_descriptions, tool_specs
from alv.world.warehouse import build

PROTOCOL = "2025-06-18"


def handle(msg: dict, tools: Tools, levers: set[str]) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method")
    if mid is None:  # a notification: no reply
        return None
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "analytics-agent-levers", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": [{"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"]}
                            for s in tool_specs(levers)]}
    elif method == "tools/call":
        p = msg.get("params") or {}
        if p.get("name") not in {s["name"] for s in tool_specs(levers)}:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {p.get('name')}"}}
        c = tools.call(p["name"], p.get("arguments") or {})
        text = c.error if c.error else json.dumps(c.output, default=str)
        result = {"content": [{"type": "text", "text": text}], "isError": c.error is not None}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levers", default="descriptions,metric_catalog")
    a = ap.parse_args()
    levers = {x for x in a.levers.split(",") if x}
    cfg = platform()
    sess = build(world()["warehouse"])
    set_descriptions(sess, "descriptions" in levers)
    tools = Tools(sess, cfg, metric_catalog="metric_catalog" in levers)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line), tools, levers)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
