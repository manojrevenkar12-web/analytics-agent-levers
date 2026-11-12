"""Every lever setting on the same questions: outcomes, cost, time and Langfuse-shaped traces."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from alv.agent.loop import run as run_agent
from alv.evals.score import judge
from alv.sim.planner import planner_factory
from alv.sim.user import responder
from alv.sql import catalog
from alv.tools import Tools, set_descriptions
from alv.world.questions import generate
from alv.world.warehouse import build


def settings(cfg: dict) -> dict[str, frozenset[str]]:
    order = cfg["levers"]["order"]
    out = {"baseline": frozenset()}
    out.update({lv: frozenset([lv]) for lv in order})
    out["all"] = frozenset(order)
    out.update({f"all_but_{lv}": frozenset(order) - {lv} for lv in order})  # what each lever adds on top of the rest
    return out


@dataclass
class Row:
    setting: str
    qid: str
    kind: str
    verdict: str
    asked: int
    turns: int
    usd: float
    seconds: float
    confidence: float
    outcome: object


def evaluate_seed(world_cfg: dict, platform_cfg: dict, seed: int, keep_outcomes: bool = False) -> dict:
    sess = build(world_cfg["warehouse"])
    qcfg = {**world_cfg["questions"], "seed": world_cfg["questions"]["seed"] * 1000 + seed}
    qs = generate(qcfg, sess, catalog(platform_cfg, verified_only=False), extra_terms=world_cfg.get("extra_terms"))
    make = planner_factory(world_cfg["model"], platform_cfg["levers"], seed)
    rows: list[Row] = []
    for name, levers in settings(platform_cfg).items():
        set_descriptions(sess, "descriptions" in levers)
        tools = Tools(sess, platform_cfg, metric_catalog="metric_catalog" in levers)
        for q, t in qs:
            o = run_agent(q.qid, q.text, make(q.qid), tools, responder(t, platform_cfg, world_cfg), set(levers), platform_cfg)
            rows.append(Row(name, q.qid, t.kind, judge(o, t), o.asked, len(o.turns), o.usd(platform_cfg["model"]),
                            o.seconds, o.confidence, o if keep_outcomes else None))
    sess.close()
    shutil.rmtree(sess.workdir, ignore_errors=True)
    return {"seed": seed, "questions": [(q, t) for q, t in qs], "rows": rows}
