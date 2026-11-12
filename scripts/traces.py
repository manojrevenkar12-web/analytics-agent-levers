"""Write a sample of agent runs as Langfuse ingestion events (reports/traces_sample.jsonl), or send them to a Langfuse
project when LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set and --send is given."""

from __future__ import annotations

import argparse
import json
import shutil

from alv.agent.loop import run
from alv.config import ROOT, platform, world
from alv.evals.score import judge
from alv.sim.planner import planner_factory
from alv.sim.user import responder
from alv.sql import catalog
from alv.tools import Tools, set_descriptions
from alv.trace import events, send
from alv.world.questions import generate
from alv.world.warehouse import build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=int, default=12)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    cfg, w = platform(), world()
    seed = cfg["eval"]["seeds"][0]
    sess = build(w["warehouse"])
    qs = generate({**w["questions"], "seed": w["questions"]["seed"] * 1000 + seed}, sess, catalog(cfg, verified_only=False))
    make = planner_factory(w["model"], cfg["levers"], seed)
    batch = []
    for setting, levers in (("baseline", set()), ("all", set(cfg["levers"]["order"]))):
        set_descriptions(sess, "descriptions" in levers)
        tools = Tools(sess, cfg, metric_catalog="metric_catalog" in levers)
        for q, t in qs[: a.questions]:
            o = run(q.qid, q.text, make(q.qid), tools, responder(t, cfg, w), levers, cfg)
            batch += events(f"{setting}-{seed}", q.text, o, cfg["model"], setting, judge(o, t))
    sess.close()
    shutil.rmtree(sess.workdir, ignore_errors=True)
    (ROOT / "reports" / "traces_sample.jsonl").write_text("".join(json.dumps(e) + "\n" for e in batch))
    print(len(batch), "events")
    if a.send:
        print(send(batch))


if __name__ == "__main__":
    main()
