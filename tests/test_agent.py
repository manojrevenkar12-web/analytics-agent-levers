"""The loop, the stand-in planner and the scorer."""

from __future__ import annotations

import ast
from pathlib import Path

from alv.agent.loop import Action, run
from alv.evals.score import judge, same_rows
from alv.sim.planner import SimPlanner, parse_period, planner_factory
from alv.sql import catalog
from alv.tools import Tools, set_descriptions
from alv.world.questions import Truth, generate

from helpers import cfg, session, small_world

ROOT = Path(__file__).resolve().parents[1]


def scripted(actions):
    def planner(question, levers):
        for a in actions:  # noqa: UP028 - a list iterator cannot take the observations the loop sends back
            yield a
    return planner


def test_tokens_cost_and_time_are_accounted_per_turn():
    c = cfg()
    o = run("q1", "How many?", scripted([Action("tool", tool="list_tables"), Action("answer", rows=[[1]])]),
            Tools(session(), c), lambda t: "", set(), c)
    assert o.kind == "answer" and len(o.turns) == 2
    assert o.turns[1].input_tokens > o.turns[0].input_tokens  # the table list is in the context now
    assert o.output_tokens == c["agent"]["output_tokens_per_turn"] + c["agent"]["answer_tokens"]
    assert o.usd(c["model"]) > 0 and o.seconds > 0


def test_asking_needs_the_clarify_lever_and_the_turn_limit_holds():
    c = cfg()
    seen = []

    def planner(question, levers):
        obs = yield Action("ask", text="Which?")
        seen.append(obs)
        while True:
            yield Action("tool", tool="list_tables")

    o = run("q", "x", planner, Tools(session(), c), lambda t: "this one", set(), c)
    assert "error" in seen[0] and o.kind == "gave_up" and len(o.turns) == c["agent"]["max_turns"] and o.asked == 0


def test_periods_parse():
    assert parse_period("revenue in Q2 2026?") == ("2026-04-01", "2026-06-30")
    assert parse_period("in February 2024") == ("2024-02-01", "2024-02-29")
    assert parse_period("in 2025.") == ("2025-01-01", "2025-12-31")
    assert parse_period("lately") is None


def test_scoring_rules():
    assert same_rows([["DE", 100.0]], [["DE", 100.3]]) and not same_rows([["DE", 100.0]], [["DE", 110.0]])
    assert not same_rows([[1]], [[1], [2]])
    from alv.agent.loop import Outcome
    ans, abst = Outcome("q", "answer", [[1]], "", 1, 0, []), Outcome("q", "abstain", None, "", 0, 0, [])
    un = Truth("unanswerable", None, None)
    assert judge(abst, un) == "correct" and judge(ans, un) == "wrong"
    t = Truth("answerable", "x", None, [[1]])
    assert judge(ans, t) == "correct" and judge(abst, t) == "missed"


def test_the_stand_in_never_reads_the_truth():
    src = (ROOT / "src/alv/sim/planner.py").read_text()
    mods = {n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom)}
    assert not any(m and ("world" in m or "evals" in m or "sim.user" in m) for m in mods)


def test_same_question_same_luck_across_settings():
    p = SimPlanner(small_world()["model"], 11, "q0001")
    assert p.u("table0") == SimPlanner(small_world()["model"], 11, "q0001").u("table0")
    assert p.u("table0") != SimPlanner(small_world()["model"], 11, "q0002").u("table0")


def outcomes(levers):
    c, w = cfg(), small_world()
    qs = generate(w["questions"], session(), catalog(c, verified_only=False))
    set_descriptions(session(), "descriptions" in levers)
    tools = Tools(session(), c, metric_catalog="metric_catalog" in levers)
    make = planner_factory(w["model"], c["levers"], 11)
    from alv.sim.user import responder
    res = [judge(run(q.qid, q.text, make(q.qid), tools, responder(t, c, w), set(levers), c), t) for q, t in qs]
    set_descriptions(session(), False)
    return res, qs


def test_every_lever_together_beats_the_baseline_and_abstaining_cuts_wrong_answers():
    base, _ = outcomes(set())
    full, _ = outcomes({"descriptions", "metric_catalog", "clarify", "abstain"})
    assert full.count("correct") > base.count("correct") + len(base) // 5
    assert full.count("wrong") < base.count("wrong") // 3


def test_unanswerable_questions_get_not_sure_with_the_abstain_lever():
    res, qs = outcomes({"descriptions", "abstain"})
    un = [r for r, (_, t) in zip(res, qs, strict=True) if t.kind == "unanswerable"]
    assert un and un.count("correct") / len(un) >= 0.8


def test_held_out_lock_matches_the_code():
    import json

    from heldout import LOCK, fingerprint
    if LOCK.exists():
        assert json.loads(LOCK.read_text())["fingerprint"] == fingerprint(), "settings or code changed after the held-out run"
