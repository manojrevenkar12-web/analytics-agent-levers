"""From outcomes to decisions: rates per lever setting, paired intervals against the baseline, and the launch gate.

Every setting answers the same questions with the same luck, so differences are paired per (seed, question) and the
interval comes from resampling questions.
"""

from __future__ import annotations

import multiprocessing as mp
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from alv.evals.run import evaluate_seed, settings


def _flat(results: list[dict]) -> dict[str, dict[tuple, object]]:
    by: dict[str, dict[tuple, object]] = defaultdict(dict)
    for r in results:
        for row in r["rows"]:
            by[row.setting][(r["seed"], row.qid)] = row
    return by


def summary(rows: list) -> dict:
    n = len(rows)
    v = [r.verdict for r in rows]
    usd = np.array([r.usd for r in rows])
    sec = np.array([r.seconds for r in rows])
    kinds = defaultdict(lambda: defaultdict(int))
    for r in rows:
        kinds[r.kind][r.verdict] += 1
    return {
        "questions": n,
        "correct": v.count("correct") / n,
        "wrong": v.count("wrong") / n,
        "missed": v.count("missed") / n,
        "gave_up": v.count("gave_up") / n,
        "asked_per_100": 100 * sum(r.asked for r in rows) / n,
        "turns": float(np.mean([r.turns for r in rows])),
        "usd_per_question": float(usd.mean()),
        "usd_p95": float(np.percentile(usd, 95)),
        "usd_per_correct": float(usd.sum() / max(v.count("correct"), 1)),
        "seconds_p50": float(np.percentile(sec, 50)),
        "seconds_p95": float(np.percentile(sec, 95)),
        "by_kind": {k: {o: c / sum(d.values()) for o, c in d.items()} | {"n": sum(d.values())} for k, d in kinds.items()},
    }


def paired(a: dict, b: dict, metric: str, draws: int, seed: int = 0) -> dict:
    """Difference b - a in the share of questions with verdict `metric`, with a 95% bootstrap interval."""
    keys = sorted(a)
    x = np.array([(b[k].verdict == metric) - (a[k].verdict == metric) for k in keys], dtype=float)
    rng = np.random.default_rng(seed)
    boots = x[rng.integers(0, len(x), (draws, len(x)))].mean(axis=1)
    return {"diff": float(x.mean()), "lo": float(np.percentile(boots, 2.5)), "hi": float(np.percentile(boots, 97.5))}


def decide(by: dict, cfg: dict) -> dict:
    g = cfg["gate"]
    base = by["baseline"]
    out = {}
    for name in [n for n in by if n != "baseline"]:
        c = paired(base, by[name], "correct", g["bootstrap"])
        w = paired(base, by[name], "wrong", g["bootstrap"], seed=1)
        sm = summary(list(by[name].values()))
        usd = sm["usd_per_question"]
        checks = [
            {"check": "correctness gain, lower end of the 95% interval", "value": c["lo"], "limit": g["min_correct_gain"],
             "ok": c["lo"] > g["min_correct_gain"]},
            {"check": "change in confidently wrong answers, upper end of the 95% interval", "value": w["hi"],
             "limit": g["max_wrong_increase"], "ok": w["hi"] <= g["max_wrong_increase"]},
            {"check": "cost per question (USD)", "value": usd, "limit": g["max_usd_per_answer"], "ok": usd <= g["max_usd_per_answer"]},
            {"check": "clarifying questions per 100 questions", "value": sm["asked_per_100"], "limit": g["max_asked_per_100"],
             "ok": sm["asked_per_100"] <= g["max_asked_per_100"]},
        ]
        out[name] = {"correct": c, "wrong": w, "checks": checks, "ship": all(x["ok"] for x in checks)}
    return out


def marginal(by: dict, cfg: dict) -> dict:
    """What each lever adds when every other lever is already on: the order to ship them in."""
    g = cfg["gate"]
    return {lv: {"correct": paired(by[f"all_but_{lv}"], by["all"], "correct", g["bootstrap"], seed=2),
                 "wrong": paired(by[f"all_but_{lv}"], by["all"], "wrong", g["bootstrap"], seed=3)}
            for lv in cfg["levers"]["order"]}


def evaluate(world_cfg: dict, cfg: dict, seeds: list[int], workers: int = 3) -> dict:
    with ProcessPoolExecutor(max_workers=min(workers, len(seeds)), mp_context=mp.get_context("spawn")) as ex:
        results = list(ex.map(evaluate_seed, [world_cfg] * len(seeds), [cfg] * len(seeds), seeds))
    by = _flat(results)
    return {
        "seeds": seeds,
        "settings": {k: sorted(v) for k, v in settings(cfg).items()},
        "summary": {k: summary(list(v.values())) for k, v in by.items()},
        "per_seed": {k: [summary([r for r in res["rows"] if r.setting == k])["correct"] for res in results] for k in by},
        "gate": decide(by, cfg),
        "marginal": marginal(by, cfg),
    }
