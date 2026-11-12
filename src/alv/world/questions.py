"""Questions people ask the data agent, and the truth about each: what it means and the right answer.

Four kinds, as in real traffic:
- answerable: the wording names one metric and one account exactly.
- ambiguous_term: a business word the company defines one way ("revenue" is net revenue from the revenue mart,
  "active customers" means a login, not a running subscription). Right: answer by the company's definition, or ask.
- ambiguous_entity: an account named by its first two words ("Acme Robotics"), which matches several. Right: ask.
- unanswerable: the warehouse has no such data (marketing spend, NPS). Right: say so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from alv.sql import Ask, Metric, build

COUNTRIES = {"DE": "Germany", "FR": "France", "NL": "the Netherlands", "UK": "the United Kingdom", "AT": "Austria",
             "CH": "Switzerland", "ES": "Spain", "IT": "Italy", "PL": "Poland"}
SEGMENTS = {"smb": "small business", "mid": "mid-market", "enterprise": "enterprise"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]

# How people phrase each metric. Exact phrasings are unambiguous; the ambiguous ones lean on a company definition.
EXACT = {
    "net_revenue": ["net revenue"],
    "gross_revenue": ["gross revenue", "billings"],
    "refunds": ["refunds"],
    "queries": ["queries run", "query volume"],
    "csat": ["CSAT", "customer satisfaction"],
    "tickets_opened": ["support tickets opened"],
    "active_accounts": ["accounts with a login"],
}
AMBIGUOUS = {"net_revenue": ["revenue", "sales"], "active_accounts": ["active customers"]}
UNANSWERABLE = ["marketing spend", "NPS", "sales pipeline", "headcount", "churn reasons"]
TEMPLATES = {
    "total": ["What was our {m}{f} {p}?", "How much {m}{f} did we have {p}?", "Give me {m}{f} {p}."],
    "grouped": ["Show {m}{f} {p} by {g}.", "Break down {m}{f} {p} by {g}."],
}


@dataclass(frozen=True)
class Question:
    qid: str
    text: str


@dataclass
class Truth:
    kind: str
    metric: str | None
    ask: Ask | None
    answer: list | None = None
    entity: str | None = None  # the account the person means
    term: str | None = None
    meta: dict = field(default_factory=dict)


def _period(rng: np.random.Generator, end_year: int) -> tuple[str, str, str]:
    r = rng.random()
    if r < 0.4:
        y = int(rng.choice([2025, 2026])) if end_year >= 2026 else 2025
        m = int(rng.integers(1, 10 if y == end_year else 13))
        last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
        return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last}", f"in {MONTHS[m - 1]} {y}"
    if r < 0.8:
        y = int(rng.choice([2024, 2025, 2026]))
        q = int(rng.integers(1, 4 if y == end_year else 5))
        ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
        return f"{y}-{3 * q - 2:02d}-01", f"{y}-{ends[q]}", f"in Q{q} {y}"
    y = int(rng.choice([2024, 2025]))
    return f"{y}-01-01", f"{y}-12-31", f"in {y}"


def run_sql(sess, sql: str) -> list:
    return json.loads(sess.query(sql, "JSONCompact").bytes())["data"]


def generate(qcfg: dict, sess, metrics: dict[str, Metric], end_year: int = 2026, extra_terms: dict | None = None
             ) -> list[tuple[Question, Truth]]:
    rng = np.random.default_rng(qcfg["seed"])
    names = [r[0] for r in run_sql(sess, "SELECT account_name FROM analytics.dim_accounts ORDER BY account_id")]
    ids = {n: i + 1 for i, n in enumerate(names)}
    ambiguous = {k: list(v) for k, v in AMBIGUOUS.items()}
    for k, v in (extra_terms or {}).items():
        ambiguous.setdefault(k, []).extend(v)
    out = []
    for i in range(qcfg["count"]):
        r = rng.random()
        start, end, ptxt = _period(rng, end_year)
        if r < qcfg["unanswerable_share"]:
            term = str(rng.choice(UNANSWERABLE))
            text = str(rng.choice(TEMPLATES["total"])).format(m=term, f="", p=ptxt)
            out.append((Question(f"q{i:04d}", text), Truth("unanswerable", None, None, term=term)))
            continue
        kind = "ambiguous_term" if r < qcfg["unanswerable_share"] + qcfg["ambiguous_share"] else "answerable"
        if kind == "ambiguous_term":
            metric = str(rng.choice(sorted(ambiguous)))
            term = str(rng.choice(ambiguous[metric]))
        else:
            metric = str(rng.choice(sorted(EXACT)))
            term = str(rng.choice(EXACT[metric]))
        filters: list = []
        ftxt = ""
        entity = None
        grouped = rng.random() < qcfg["grouped_share"]
        if not grouped and rng.random() < qcfg["entity_share"]:
            entity = names[int(rng.integers(0, len(names)))]
            filters.append(("account_id", ids[entity]))
            if kind == "answerable" and rng.random() < 0.5:
                kind = "ambiguous_entity"
                ftxt = " for " + " ".join(entity.split()[:2])
            else:
                ftxt = f" for {entity}"
        elif rng.random() < 0.35:
            if rng.random() < 0.5:
                c = str(rng.choice(sorted(COUNTRIES)))
                filters.append(("country", c))
                ftxt = f" from {COUNTRIES[c]}"
            else:
                s = str(rng.choice(sorted(SEGMENTS)))
                filters.append(("segment", s))
                ftxt = f" from {SEGMENTS[s]} customers"
        group = None
        if grouped:
            group = str(rng.choice(["month", "country", "segment"]))
            if any(k == group for k, _ in filters):  # "from Germany ... by country" is not a question people ask
                filters, ftxt = [], ""
        ask = Ask(start, end, tuple(filters), group)
        text = str(rng.choice(TEMPLATES["grouped" if group else "total"])).format(m=term, f=ftxt, p=ptxt, g=group)
        answer = run_sql(sess, build(metrics[metric], ask))
        out.append((Question(f"q{i:04d}", text[0].upper() + text[1:]),
                    Truth(kind, metric, ask, answer, entity, term)))
    return out
