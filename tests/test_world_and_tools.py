"""The warehouse has the traps it claims, and the tools are read-only, honest about descriptions and gated by levers."""

from __future__ import annotations

from alv.sql import Ask, Metric, build, catalog, quote
from alv.tools import Tools, set_descriptions
from alv.world.questions import generate, run_sql

from helpers import cfg, session, small_world


def q(sql):
    return run_sql(session(), sql)


def test_account_names_are_unique_but_have_near_duplicates():
    (n, u), = q("SELECT count(), uniqExact(account_name) FROM analytics.dim_accounts")
    assert n == u
    (dups,), = q("SELECT count() FROM (SELECT arrayStringConcat(arraySlice(splitByChar(' ', account_name), 1, 2), ' ') p,"
                 " count() c FROM analytics.dim_accounts GROUP BY p HAVING c > 1)")
    assert dups > 0


def test_the_traps_are_there():
    (last,), = q("SELECT max(issued) FROM analytics.legacy_invoices")
    assert last <= small_world()["warehouse"]["legacy_cutoff"]
    (retries,), = q("SELECT count() - uniqExact(invoice_id) FROM analytics.stg_payments")
    assert retries > 0
    (days,), = q("SELECT count() FROM analytics.tmp_revenue_backfill")
    (all_days,), = q("SELECT uniqExact(day) FROM analytics.mart_revenue_daily")
    assert 0 < days < all_days


def test_the_revenue_mart_is_net_revenue_of_paid_invoices():
    (mart,), = q("SELECT round(sum(net_revenue), 2) FROM analytics.mart_revenue_daily")
    (inv,), = q("SELECT round(sum(amount_net), 2) FROM analytics.fct_invoices WHERE status = 'paid'")
    assert abs(mart - inv) < 1.0


def test_sql_builder_escapes_and_groups():
    m = Metric("x", "fct_invoices", "count()", "", "d.issued")
    sql = build(m, Ask("2025-01-01", "2025-12-31", (("country", "D'E"),), "segment"))
    assert "JOIN analytics.dim_accounts" in sql and "'D\\'E'" in sql and "GROUP BY k" in sql
    assert quote(5) == "5"


def test_tools_are_read_only():
    t = Tools(session(), cfg())
    for bad in ["DROP TABLE analytics.dim_plans", "SELECT 1; DROP TABLE analytics.dim_plans",
                "INSERT INTO analytics.dim_plans VALUES ('x', 1)", "ALTER TABLE analytics.dim_plans DELETE WHERE 1"]:
        assert t.call("run_select_query", {"query": bad}).error
    assert t.call("describe_table", {"table": "dim_plans; DROP"}).error
    assert q("SELECT count() FROM analytics.dim_plans") == [[4]]


def test_descriptions_appear_only_when_the_lever_writes_them():
    t = Tools(session(), cfg())
    set_descriptions(session(), True)
    on = {x["name"]: x["comment"] for x in t.call("list_tables", {}).output}
    set_descriptions(session(), False)
    off = {x["name"]: x["comment"] for x in t.call("list_tables", {}).output}
    assert "Deprecated" in on["legacy_invoices"] and off["legacy_invoices"] == ""


def test_metric_catalogue_needs_the_lever_and_serves_only_verified_metrics():
    assert Tools(session(), cfg()).call("get_metric", {"term": "revenue"}).error
    t = Tools(session(), cfg(), metric_catalog=True)
    assert t.call("get_metric", {"term": "Revenue"}).output["table"] == "mart_revenue_daily"
    assert t.call("get_metric", {"term": "csat"}).output is None  # defined, not verified yet


def test_questions_carry_their_truth_and_every_kind_appears():
    qs = generate(small_world()["questions"], session(), catalog(cfg(), verified_only=False))
    kinds = {t.kind for _, t in qs}
    assert kinds == {"answerable", "ambiguous_term", "ambiguous_entity", "unanswerable"}
    for qq, t in qs:
        assert (t.answer is None) == (t.kind == "unanswerable")
        assert qq.text[0].isupper()
