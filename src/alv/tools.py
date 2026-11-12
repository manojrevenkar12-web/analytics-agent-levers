"""What the agent can do against ClickHouse: the tools the ClickHouse MCP server exposes, and the product's levers.

`list_tables`, `describe_table` and `run_select_query` read the database as any MCP client would; table and column
descriptions appear only if they exist in ClickHouse as COMMENTs. `get_metric` is the verified metric catalogue. Every
query is read-only, row-limited and timed.
"""

from __future__ import annotations

import json
import re
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from alv.config import ROOT

READ_ONLY = re.compile(r"^\s*(SELECT|WITH)\b", re.I)
FORBIDDEN = re.compile(r"\b(INSERT|ALTER|DROP|CREATE|TRUNCATE|DELETE|UPDATE|RENAME|GRANT|SYSTEM|KILL|OPTIMIZE)\b", re.I)


def descriptions() -> dict:
    return tomllib.loads((ROOT / "config" / "descriptions.toml").read_text(encoding="utf-8"))


def set_descriptions(sess, on: bool, db: str = "analytics") -> None:
    """Write (or clear) the data team's descriptions as ClickHouse COMMENTs: the descriptions lever."""
    d = descriptions()
    tables = [r[0] for r in json.loads(sess.query(f"SELECT name FROM system.tables WHERE database = '{db}'",
                                                  "JSONCompact").bytes())["data"]]
    for t in tables:
        c = d["tables"].get(t, "") if on else ""
        sess.query(f"ALTER TABLE {db}.{t} MODIFY COMMENT '{c.replace(chr(39), chr(92) + chr(39))}'")
    for key, c in d["columns"].items():
        t, col = key.split(".")
        if t in tables:
            c = c if on else ""
            sess.query(f"ALTER TABLE {db}.{t} COMMENT COLUMN {col} '{c.replace(chr(39), chr(92) + chr(39))}'")


@dataclass
class Call:
    tool: str
    args: dict
    output: object
    error: str | None
    ms: float


@dataclass
class Tools:
    sess: object
    cfg: dict
    metric_catalog: bool = False
    db: str = "analytics"
    max_rows: int = 200
    calls: list[Call] = field(default_factory=list)

    def _q(self, sql: str) -> tuple[list, float]:
        t = time.perf_counter()
        r = self.sess.query(sql, "JSONCompact")
        return json.loads(r.bytes())["data"], (time.perf_counter() - t) * 1000

    def call(self, tool: str, args: dict) -> Call:
        t = time.perf_counter()
        try:
            out = getattr(self, f"_{tool}")(**args)
            c = Call(tool, args, out, None, (time.perf_counter() - t) * 1000)
        except Exception as e:  # the agent sees the error and may try again, as with a real database
            c = Call(tool, args, None, str(e).split("\n")[0][:300], (time.perf_counter() - t) * 1000)
        self.calls.append(c)
        return c

    # -- the ClickHouse MCP server's tools ------------------------------------------------------------------------
    def _list_tables(self) -> list[dict]:
        rows, _ = self._q(f"SELECT name, comment, total_rows FROM system.tables WHERE database = '{self.db}' ORDER BY name")
        return [{"name": n, "comment": c, "rows": r} for n, c, r in rows]

    def _describe_table(self, table: str) -> list[dict]:
        if not re.fullmatch(r"\w+", table):
            raise ValueError("table names are identifiers")
        rows, _ = self._q(f"SELECT name, type, comment FROM system.columns WHERE database = '{self.db}' AND table = '{table}'"
                          " ORDER BY position")
        if not rows:
            raise ValueError(f"no table {table}")
        return [{"name": n, "type": t, "comment": c} for n, t, c in rows]

    def _run_select_query(self, query: str) -> dict:
        if not READ_ONLY.match(query) or FORBIDDEN.search(query):
            raise PermissionError("only read-only SELECT queries are allowed")
        rows, ms = self._q(f"SELECT * FROM ({query}) LIMIT {self.max_rows}")
        return {"rows": rows, "elapsed_ms": round(ms, 2)}

    # -- product levers -------------------------------------------------------------------------------------------
    def _get_metric(self, term: str) -> dict | None:
        if not self.metric_catalog:
            raise PermissionError("the metric catalogue is not enabled")
        t = term.lower().strip()
        for name, m in self.cfg["metrics"].items():
            if m["verified"] and t in [x.lower() for x in m["terms"]]:
                return {"metric": name, "description": m["description"], "table": m["table"], "agg": m["agg"],
                        "filter": m["filter"], "date": m["date"]}
        return None


def tool_specs(levers: set[str]) -> list[dict]:
    """The tools in the shape a model API takes them (JSON Schema inputs)."""
    specs = [
        {"name": "list_tables", "description": "List tables in the analytics database with their descriptions.",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "describe_table", "description": "Columns of a table with types and descriptions.",
         "input_schema": {"type": "object", "properties": {"table": {"type": "string"}}, "required": ["table"]}},
        {"name": "run_select_query", "description": "Run a read-only ClickHouse SELECT and return rows.",
         "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    ]
    if "metric_catalog" in levers:
        specs.append({"name": "get_metric", "description": "Look up the company's verified definition of a business term.",
                      "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}})
    return specs


def load_root() -> Path:
    return ROOT
