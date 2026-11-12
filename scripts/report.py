"""Builds the README results block and the dashboard's data from reports/*.json. Nothing in the README is typed by hand."""

from __future__ import annotations

import json
import re

from alv.config import ROOT, platform

ORDER = ["baseline", "descriptions", "metric_catalog", "clarify", "abstain", "all"]
KINDS = {"answerable": "Clear questions", "ambiguous_term": "Company-defined words (\"revenue\")",
         "ambiguous_entity": "Account named by two words", "unanswerable": "Data we do not have"}


def load(name):
    p = ROOT / "reports" / name
    return json.loads(p.read_text()) if p.exists() else None


def label(cfg, k):
    if k == "baseline":
        return "Baseline: schema names only"
    if k == "all":
        return "All four levers"
    if k.startswith("all_but_"):
        return f"All but {cfg['levers']['labels'][k[8:]].lower()}"
    return cfg["levers"]["labels"][k]


def table(rep, cfg, names):
    out = ["| Setting | Correct | Confidently wrong | Not sure | Questions asked per 100 | Cost per question | "
           "Cost per correct answer | p95 time |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in names:
        s = rep["summary"][k]
        out.append(f"| {label(cfg, k)} | {s['correct']:.1%} | {s['wrong']:.1%} | {s['missed']:.1%} | {s['asked_per_100']:.0f} | "
                   f"${s['usd_per_question']:.4f} | ${s['usd_per_correct']:.4f} | {s['seconds_p95']:.1f} s |")
    return out


def gate(rep, cfg):
    out = ["| Lever, against the baseline | Correctness gain (95% interval) | Change in confidently wrong | Asked per 100 | Decision |",
           "|---|---:|---:|---:|---|"]
    for k in ORDER[1:]:
        g = rep["gate"][k]
        c, w = g["correct"], g["wrong"]
        failed = [x["check"] for x in g["checks"] if not x["ok"]]
        why = "ship" if g["ship"] else "hold: " + "; ".join(failed)
        out.append(f"| {label(cfg, k)} | {c['diff']:+.1%} ({c['lo']:+.1%} to {c['hi']:+.1%}) | {w['diff']:+.1%} | "
                   f"{rep['summary'][k]['asked_per_100']:.0f} | {why} |")
    return out


def marginal(rep, cfg):
    out = ["| Lever | Correctness it adds on top of the other three | Change in confidently wrong |", "|---|---:|---:|"]
    for k, v in sorted(rep["marginal"].items(), key=lambda kv: -kv[1]["correct"]["diff"]):
        out.append(f"| {cfg['levers']['labels'][k]} | {v['correct']['diff']:+.1%} ({v['correct']['lo']:+.1%} to "
                   f"{v['correct']['hi']:+.1%}) | {v['wrong']['diff'] + 0.0:+.1%} |")
    return out


def kinds(rep):
    out = ["| Question kind | Baseline correct | All levers correct | All levers: not sure |", "|---|---:|---:|---:|"]
    b, a = rep["summary"]["baseline"]["by_kind"], rep["summary"]["all"]["by_kind"]
    for k, lab in KINDS.items():
        out.append(f"| {lab} ({a[k]['n']} questions) | {b[k].get('correct', 0):.0%} | {a[k].get('correct', 0):.0%} | "
                   f"{a[k].get('missed', 0):.0%} |")
    return out


def main() -> None:
    cfg = platform()
    ev, ho, tr = load("evaluation.json"), load("heldout.json"), ROOT / "reports" / "traces_sample.jsonl"
    s = ev["summary"]
    n = s["baseline"]["questions"]
    lines = [
        f"{n:,} questions ({n // len(ev['seeds'])} per seed, seeds {', '.join(map(str, ev['seeds']))}) against a ClickHouse warehouse "
        "of 11 tables, every setting on the same questions with the same luck. Answers are judged on their result sets.",
        "", "**Each lever, and all four together**", "", *table(ev, cfg, ORDER), "",
        "**Launch gate** (`config/platform.toml [gate]`)", "", *gate(ev, cfg), "",
        "**What each lever adds when the other three are already on** (the order to ship them)", "", *marginal(ev, cfg), "",
        "**Where the errors were**", "", *kinds(ev),
    ]
    if ho:
        lines += ["", f"**Held-out company** (`config/world_heldout.toml`, run once on {ho['ran_at'][:10]}): other data, more "
                  "ambiguous questions, and words nobody tuned for (\"turnover\", \"engaged customers\")", "",
                  *table(ho, cfg, ORDER), "", *kinds(ho)]
    if tr.exists():
        ev_n = sum(1 for _ in tr.open())
        lines += ["", f"Traces: `reports/traces_sample.jsonl` holds {ev_n} Langfuse ingestion events (traces, generations with "
                  "token usage and cost, tool spans, and the verdict as a score); `python scripts/traces.py --send` posts them "
                  "to a Langfuse project."]
    block = "\n".join(lines)
    readme = ROOT / "README.md"
    readme.write_text(re.sub(r"<!-- results:start -->.*<!-- results:end -->", f"<!-- results:start -->\n{block}\n<!-- results:end -->",
                             readme.read_text(), flags=re.S))
    web = {"order": ORDER, "labels": {k: label(cfg, k) for k in ev["summary"]}, "kinds": KINDS, "summary": ev["summary"],
           "gate": ev["gate"], "marginal": ev["marginal"], "per_seed": ev["per_seed"], "seeds": ev["seeds"],
           "lever_labels": cfg["levers"]["labels"], "model": cfg["model"],
           "heldout": {"summary": ho["summary"], "gate": ho["gate"], "ran_at": ho["ran_at"]} if ho else None}
    out = ROOT / "web" / "public" / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(web) + "\n")
    print(block)


if __name__ == "__main__":
    main()
