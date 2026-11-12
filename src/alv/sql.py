"""One way to turn a metric definition, a period, filters and a breakdown into ClickHouse SQL.

The agent uses it when it has a definition (from the catalogue, or from the person after a clarifying question); the
scorer uses it with the company's definitions to compute the right answer. Values are escaped, not interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GROUPS = {"month": "toStartOfMonth({date})", "country": "a.country", "segment": "a.segment"}


@dataclass(frozen=True)
class Metric:
    name: str
    table: str
    agg: str
    filter: str
    date: str


@dataclass(frozen=True)
class Ask:
    """A structured question: what to compute, over which days, for whom, broken down by what."""

    start: str
    end: str
    filters: tuple[tuple[str, str | int], ...] = field(default_factory=tuple)
    group: str | None = None


def quote(v: str | int) -> str:
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def build(m: Metric, ask: Ask) -> str:
    needs_accounts = ask.group in ("country", "segment") or any(k in ("country", "segment") for k, _ in ask.filters)
    join = " JOIN analytics.dim_accounts a ON a.account_id = d.account_id" if needs_accounts else ""
    where = [f"{m.date} BETWEEN {quote(ask.start)} AND {quote(ask.end)}"]
    if m.filter:
        where.append(m.filter)
    for k, v in ask.filters:
        col = "d.account_id" if k == "account_id" else f"a.{k}"
        where.append(f"{col} = {quote(v)}")
    sel = m.agg
    tail = ""
    if ask.group:
        g = GROUPS[ask.group].format(date=m.date)
        sel = f"{g} AS k, {m.agg} AS v"
        tail = " GROUP BY k ORDER BY k"
    return f"SELECT {sel} FROM analytics.{m.table} d{join} WHERE {' AND '.join(where)}{tail}"


def catalog(cfg: dict, verified_only: bool = True) -> dict[str, Metric]:
    out = {}
    for name, d in cfg["metrics"].items():
        if verified_only and not d["verified"]:
            continue
        out[name] = Metric(name, d["table"], d["agg"], d["filter"], d["date"])
    return out
