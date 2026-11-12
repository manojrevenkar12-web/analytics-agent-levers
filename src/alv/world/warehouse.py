"""The company's warehouse, built in ClickHouse from deterministic hashes so the same seed gives the same data.

It is shaped like a real one, traps included: a deprecated invoice table that stopped in 2025, a staging payments table
with retried rows, a half-finished revenue backfill, a subscriptions table that is not where "active" is defined, and
account names with near-duplicates. Which table answers what is in the company's metric definitions, not in the names.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from chdb import session as chs

ROTATING = "cityHash64(number, {seed}, {salt})"


def _h(salt: int, seed: int, col: str = "number") -> str:
    return f"cityHash64({col}, {seed}, {salt})"


def _u(salt: int, seed: int, col: str = "number") -> str:
    """A uniform number in [0, 1) from a hash."""
    return f"({_h(salt, seed, col)} % 1000000) / 1000000.0"


def ddl(w: dict) -> list[str]:
    s = w["seed"]
    n = w["accounts"]
    start, end = w["start"], w["end"]
    days = f"dateDiff('day', toDate('{start}'), toDate('{end}')) + 1"
    countries = "['DE','DE','DE','FR','NL','UK','UK','AT','CH','ES','IT','PL']"
    segments = "['smb','smb','smb','mid','mid','enterprise']"
    first = "['Acme','Nordlicht','Blauwal','Kraftwerk','Helix','Orbit','Vektor','Lumen','Atlas','Quanta','Falke','Rhein']"
    second = "['Robotics','Logistics','Analytics','Foods','Mobility','Health','Energy','Retail','Labs','Systems']"
    legal = "['GmbH','AG','SE','Ltd','BV','SAS']"
    months = f"dateDiff('month', toDate('{start}'), toDate('{end}')) + 1"
    inv_rows = int(n * w["invoices_per_account_month"] * 33)
    return [
        "CREATE DATABASE IF NOT EXISTS analytics",
        "CREATE TABLE analytics.dim_accounts (account_id UInt32, account_name String, country LowCardinality(String),"
        " segment LowCardinality(String), created Date) ENGINE = MergeTree ORDER BY account_id",
        f"INSERT INTO analytics.dim_accounts SELECT number + 1,"
        f" concat({first}[(number * 7 + {s}) % 720 % 12 + 1], ' ', {second}[intDiv((number * 7 + {s}) % 720, 12) % 10 + 1],"
        f" ' ', {legal}[intDiv((number * 7 + {s}) % 720, 120) + 1]),"  # unique names; same first two words recur
        f" {countries}[{_h(4, s)} % 12 + 1], {segments}[{_h(5, s)} % 6 + 1],"
        f" toDate('{start}') + toIntervalDay({_h(6, s)} % 500) FROM numbers({n})",
        "CREATE TABLE analytics.fct_invoices (invoice_id UInt64, account_id UInt32, issued Date, amount_gross Float64,"
        " amount_net Float64, tax Float64, status LowCardinality(String)) ENGINE = MergeTree ORDER BY (issued, account_id)",
        f"INSERT INTO analytics.fct_invoices SELECT number + 1, account_id, issued, gross, round(gross * (1 - disc) / 1.19, 2),"
        f" round(gross - gross / 1.19, 2), status FROM (SELECT number, {_h(10, s)} % {n} + 1 AS account_id,"
        f" toDate('{start}') + toIntervalDay({_h(11, s)} % ({days})) AS issued,"
        f" round(200 + {_u(12, s)} * {_u(13, s)} * 24000, 2) AS gross, {_u(14, s)} * 0.15 AS disc,"
        f" multiIf({_u(15, s)} < 0.82, 'paid', {_u(15, s)} < 0.88, 'open', {_u(15, s)} < 0.95, 'void', 'refunded') AS status"
        f" FROM numbers({inv_rows}))",
        "CREATE TABLE analytics.legacy_invoices (invoice_id UInt64, account_id UInt32, issued Date, amount Float64,"
        " status_code UInt8) ENGINE = MergeTree ORDER BY issued",
        f"INSERT INTO analytics.legacy_invoices SELECT invoice_id, account_id, issued, amount_gross,"
        f" multiIf(status = 'paid', 1, status = 'open', 0, status = 'void', 2, 3) FROM analytics.fct_invoices"
        f" WHERE issued <= '{w['legacy_cutoff']}'",
        "CREATE TABLE analytics.stg_payments (payment_id UInt64, invoice_id UInt64, account_id UInt32, paid_at DateTime,"
        " amount Float64) ENGINE = MergeTree ORDER BY paid_at",
        "INSERT INTO analytics.stg_payments SELECT invoice_id * 10, invoice_id, account_id,"
        " toDateTime(issued) + toIntervalHour(36), amount_gross FROM analytics.fct_invoices WHERE status IN ('paid', 'refunded')",
        f"INSERT INTO analytics.stg_payments SELECT invoice_id * 10 + 1, invoice_id, account_id,"
        f" toDateTime(issued) + toIntervalHour(37), amount_gross FROM analytics.fct_invoices WHERE status = 'paid'"
        f" AND {_u(16, s, 'invoice_id')} < {w['payment_retry_share']}",
        "CREATE TABLE analytics.mart_revenue_daily (day Date, account_id UInt32, net_revenue Float64)"
        " ENGINE = MergeTree ORDER BY (day, account_id)",
        "INSERT INTO analytics.mart_revenue_daily SELECT issued, account_id, round(sum(amount_net), 2)"
        " FROM analytics.fct_invoices WHERE status = 'paid' GROUP BY issued, account_id",
        "CREATE TABLE analytics.tmp_revenue_backfill (day Date, revenue Float64) ENGINE = MergeTree ORDER BY day",
        f"INSERT INTO analytics.tmp_revenue_backfill SELECT day, sum(net_revenue) FROM analytics.mart_revenue_daily"
        f" WHERE {_u(17, s, 'toUInt32(day)')} < {w['backfill_share']} GROUP BY day",
        "CREATE TABLE analytics.dim_plans (plan String, list_price_monthly Float64) ENGINE = MergeTree ORDER BY plan",
        "INSERT INTO analytics.dim_plans VALUES ('starter', 99), ('team', 490), ('business', 1900), ('enterprise', 7500)",
        "CREATE TABLE analytics.fct_subscriptions (account_id UInt32, plan String, mrr Float64, started Date,"
        " ended Nullable(Date)) ENGINE = MergeTree ORDER BY account_id",
        f"INSERT INTO analytics.fct_subscriptions SELECT account_id, plan, p.list_price_monthly, created,"
        f" if({_u(20, s, 'account_id')} < 0.25, created + toIntervalDay(90 + {_h(21, s, 'account_id')} % 700), NULL)"
        f" FROM (SELECT account_id, created, ['starter','team','business','enterprise'][{_h(22, s, 'account_id')} % 4 + 1] AS plan"
        f" FROM analytics.dim_accounts) x JOIN analytics.dim_plans p USING plan",
        "CREATE TABLE analytics.fct_usage_daily (day Date, account_id UInt32, queries UInt64, gb_scanned Float64)"
        " ENGINE = MergeTree ORDER BY (day, account_id)",
        f"INSERT INTO analytics.fct_usage_daily SELECT day, account_id, 20 + {_h(30, s, 'k')} % 4000,"
        f" round({_u(31, s, 'k')} * 900, 2) FROM (SELECT toDate('{start}') + toIntervalDay(intDiv(number, {n})) AS day,"
        f" number % {n} + 1 AS account_id, number AS k FROM numbers(({days}) * {n})) WHERE {_u(32, s, 'k')} < {w['usage_share']}",
        "CREATE TABLE analytics.raw_events (ts DateTime, account_id UInt32, user_id UInt32, event LowCardinality(String))"
        " ENGINE = MergeTree ORDER BY ts",
        f"INSERT INTO analytics.raw_events SELECT toDateTime('{start} 00:00:00') + toIntervalSecond({_h(40, s)} % (({days}) * 86400)),"
        f" {_h(41, s)} % {n} + 1, {_h(42, s)} % 20000 + 1,"
        f" ['login','login','query','export','invite','dashboard_view'][{_h(43, s)} % 6 + 1]"
        f" FROM numbers({n * w['events_per_account']})",
        "CREATE TABLE analytics.fct_support_tickets (ticket_id UInt32, account_id UInt32, opened DateTime,"
        " closed Nullable(DateTime), priority LowCardinality(String), csat Nullable(UInt8)) ENGINE = MergeTree ORDER BY opened",
        f"INSERT INTO analytics.fct_support_tickets SELECT number + 1, {_h(50, s)} % {n} + 1, opened,"
        f" if({_u(51, s)} < 0.9, opened + toIntervalHour(2 + {_h(52, s)} % 200), NULL),"
        f" ['low','normal','normal','high','urgent'][{_h(53, s)} % 5 + 1],"
        f" if({_u(54, s)} < 0.55, toUInt8(1 + least(4, floor({_u(55, s)} * {_u(56, s)} * 4 + {_u(57, s)} * 2.2))), NULL)"
        f" FROM (SELECT number, toDateTime('{start} 00:00:00') + toIntervalSecond({_h(58, s)} % (({days}) * 86400)) AS opened"
        f" FROM numbers({w['tickets']}))",
        f"SELECT {months}",
    ]


def build(w: dict, path: Path | None = None) -> chs.Session:
    """A ClickHouse session holding the warehouse. With a path, an existing build is reused."""
    if path is not None and (path / ".built").exists():
        return chs.Session(str(path))
    if path is None:  # a private directory: two processes must never share chDB's default working directory
        path = Path(tempfile.mkdtemp(prefix="alv-ch-"))
    path.mkdir(parents=True, exist_ok=True)
    sess = chs.Session(str(path))
    sess.query("DROP DATABASE IF EXISTS analytics")
    for stmt in ddl(w):
        sess.query(stmt)
    (path / ".built").write_text("ok")
    sess.workdir = path
    return sess
