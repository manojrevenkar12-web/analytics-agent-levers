"""The stand-in for the model: a seeded policy that does what an LLM agent does with what it can see.

It reads the question, explores the schema through the same tools a real agent gets, picks tables and columns by the
words it can see in names and descriptions, guesses where nothing tells it, and builds SQL. Its mistakes are the
documented ones of analytics agents: the wrong table among look-alikes, the wrong amount column, a forgotten status
filter, the first of several matching accounts. It never sees the truth; every lever helps only by changing what the
tools return or by letting it ask. Its random draws are tied to (seed, question, decision), so two lever settings
face the same luck on the same question.
"""

from __future__ import annotations

import hashlib
import math
import re

from alv.agent.loop import Action
from alv.sql import Ask, Metric, build

PENALTY_WORDS = {"deprecated", "staging", "temporary", "partial", "incomplete", "retried"}
MONEY = {"revenue", "net_revenue", "gross_revenue", "refunds"}
VAGUE = {"revenue", "active_accounts"}
COUNTRIES = {"germany": "DE", "france": "FR", "the netherlands": "NL", "the united kingdom": "UK", "austria": "AT",
             "switzerland": "CH", "spain": "ES", "italy": "IT", "poland": "PL"}
SEGMENTS = {"small business": "smb", "mid-market": "mid", "enterprise": "enterprise"}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))


def parse_period(q: str) -> tuple[str, str] | None:
    s = q.lower()
    m = re.search(r"in (" + "|".join(MONTHS) + r") (\d{4})", s)
    if m:
        mo, y = MONTHS.index(m.group(1)) + 1, int(m.group(2))
        last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
        return f"{y}-{mo:02d}-01", f"{y}-{mo:02d}-{last}"
    m = re.search(r"in q([1-4]) (\d{4})", s)
    if m:
        q_, y = int(m.group(1)), m.group(2)
        return f"{y}-{3 * q_ - 2:02d}-01", f"{y}-" + {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[q_]
    m = re.search(r"in (\d{4})", s)
    if m:
        return f"{m.group(1)}-01-01", f"{m.group(1)}-12-31"
    return None


class SimPlanner:
    def __init__(self, mcfg: dict, seed: int, qid: str, temperature_scale: float = 1.0) -> None:
        self.m = mcfg
        self.seed = seed
        self.qid = qid
        self.vocab = mcfg["vocabulary"]
        self.phrases = sorted(mcfg["phrases"].items(), key=lambda kv: -len(kv[0]))
        self.t = mcfg["temperature"] * temperature_scale

    def u(self, name: str) -> float:
        h = hashlib.sha256(f"{self.m['seed']}|{self.seed}|{self.qid}|{name}".encode()).digest()
        return int.from_bytes(h[:8], "big") / 2**64

    def pick(self, name: str, probs: list[float]) -> int:
        r, acc = self.u(name), 0.0
        for i, p in enumerate(probs):
            acc += p
            if r < acc:
                return i
        return len(probs) - 1

    def softmax(self, scores: list[float]) -> list[float]:
        mx = max(scores)
        e = [math.exp((s - mx) / max(self.t, 1e-6)) for s in scores]
        z = sum(e)
        return [x / z for x in e]

    # -- reading the question ----------------------------------------------------------------------------------------
    def term(self, q: str) -> tuple[str, str | None]:
        s = q.lower()
        for phrase, key in self.phrases:
            if re.search(r"\b" + re.escape(phrase) + r"\b", s):
                return phrase, key
        m = re.match(r"(?:what was our|how much|give me|show|break down) (.+?)(?: for | from | in |\.)", s)
        return (m.group(1) if m else s), None

    def ask_struct(self, q: str) -> tuple[Ask | None, str | None]:
        period = parse_period(q)
        if period is None:
            return None, None
        start, end = period
        if self.u("parse") < self.m["parse_error"]:  # misreads the period: shifts it by a year
            start, end = str(int(start[:4]) - 1) + start[4:], str(int(end[:4]) - 1) + end[4:]
        s = q.lower()
        filters = []
        for name, code in COUNTRIES.items():
            if f"from {name}" in s:
                filters.append(("country", code))
        for name, code in SEGMENTS.items():
            if f"from {name} customers" in s:
                filters.append(("segment", code))
        group = None
        m = re.search(r"by (month|country|segment)", s)
        if m:
            group = m.group(1)
        ent = re.search(r" for (.+?) (?:did we|in )", q)
        return Ask(start, end, tuple(filters), group), (ent.group(1) if ent else None)

    # -- the plan ----------------------------------------------------------------------------------------------------
    def __call__(self, question: str, levers: set[str]):
        phrase, key = self.term(question)
        want = set(self.vocab.get(key, [])) | words(phrase)
        ask, entity = self.ask_struct(question)
        if ask is None:
            yield Action("abstain", text="I could not tell which period you mean.", confidence=0.0)
            return
        confidence = 1.0
        metric = None
        if "metric_catalog" in levers:
            obs = yield Action("tool", tool="get_metric", args={"term": phrase})
            got = obs.get("result")
            if got:
                metric = Metric(got["metric"], got["table"], got["agg"], got["filter"], got["date"])
        asked_term = False
        tried: set[str] = set()
        account_id = None
        if entity:
            esc = entity.replace("'", "\\'")
            obs = yield Action("tool", tool="run_select_query", args={"query": "SELECT account_id, account_name FROM "
                               f"analytics.dim_accounts WHERE account_name ILIKE '%{esc}%' ORDER BY account_id"})
            rows = (obs.get("result") or {}).get("rows", [])
            exact = [r for r in rows if r[1].lower() == entity.lower()]
            if exact:
                account_id = exact[0][0]
            elif len(rows) > 1 and "clarify" in levers:
                reply = (yield Action("ask", text=f"Which account do you mean: {', '.join(r[1] for r in rows[:6])}?"))
                chosen = [r for r in rows if r[1].lower() == str(reply.get("reply", "")).lower()]
                account_id = (chosen or rows)[0][0]
            elif rows:
                account_id = rows[0][0]
                confidence *= 1 / len(rows)
            else:
                confidence *= 0.1
            if account_id is not None:
                ask = Ask(ask.start, ask.end, ask.filters + (("account_id", int(account_id)),), ask.group)
        for attempt in range(3):
            m_conf = 1.0
            if metric is None:
                tables = (yield Action("tool", tool="list_tables", args={})).get("result") or []
                cands = [t for t in tables if t["name"] not in tried]
                probs = self.table_probs(cands, want)
                if ("clarify" in levers and not asked_term and len(probs) > 1
                        and (key in VAGUE or sorted(probs)[-1] - sorted(probs)[-2] < self.m_clarify)):
                    asked_term = True
                    reply = (yield Action("ask", text=f"What do you mean by '{phrase}'?")).get("reply", "")
                    want |= words(reply)
                    probs = self.table_probs(cands, want)
                i = self.pick(f"table{attempt}", probs)
                table = cands[i]
                m_conf *= probs[i]
                cols = (yield Action("tool", tool="describe_table", args={"table": table["name"]})).get("result") or []
                metric, c_conf = yield from self.choose_metric(key, want, table, cols)
                m_conf *= c_conf
            sql = build(metric, ask)
            conf = confidence * m_conf
            if "abstain" in levers and conf < self.floor:
                yield Action("abstain", text="I am not sure enough to answer this.", sql=sql, confidence=conf)
                return
            obs = yield Action("tool", tool="run_select_query", args={"query": sql})
            if obs.get("error"):
                tried.add(metric.table)
                metric = None
                continue
            yield Action("answer", rows=obs["result"]["rows"], sql=sql, confidence=conf)
            return
        yield Action("abstain", text="Every query I tried failed.", confidence=0.0)

    floor = 0.55
    m_clarify = 0.25

    def table_probs(self, tables: list[dict], want: set[str]) -> list[float]:
        scores = []
        for t in tables:
            name, comment = words(t["name"]), words(t.get("comment") or "")
            s = len(want & name) + 0.6 * len(want & comment)
            if comment & PENALTY_WORDS or "do not use" in (t.get("comment") or "").lower():
                s -= 3.0
            if f"use this for {next(iter(sorted(want & comment)), '~')}" in (t.get("comment") or "").lower():
                s += 1.0
            scores.append(s)
        return self.softmax(scores) if scores else []

    def choose_metric(self, key, want, table, cols):
        name = table["name"]
        tcomment = (table.get("comment") or "").lower()
        numeric = [c for c in cols if re.match(r"(Nullable\()?(Float|UInt|Int|Decimal)", c["type"])
                   and not c["name"].endswith("_id") and c["name"] not in ("status_code",)]
        dates = [c for c in cols if "Date" in c["type"]]
        conf = 1.0
        if not dates:
            date = "d.day"
        else:
            named = [c for c in dates if want & words(c["name"])]  # "tickets opened" -> the opened column
            told = [c for c in dates if key == "csat" and ("counted on this date" in (c["comment"] or "").lower()
                                                           or f"by {c['name']} date" in tcomment)]
            date_col = (named or told or dates)[0]["name"]
            date = f"toDate(d.{date_col})" if "DateTime" in next(c["type"] for c in dates if c["name"] == date_col) \
                else f"d.{date_col}"
        flt = ""
        colnames = {c["name"] for c in cols}
        if key == "tickets_opened":
            agg = "count()"
        elif key == "active_accounts":
            agg = "uniqExact(d.account_id)" if "account_id" in colnames else "count()"
        elif not numeric:
            agg, conf = "count()", 0.3
        else:
            sc = [len(want & words(c["name"])) + 0.6 * len(want & words(c["comment"] or "")) for c in numeric]
            probs = self.softmax(sc)
            i = self.pick("column", probs)
            col = numeric[i]["name"]
            conf *= probs[i]
            fn = "avg" if key == "csat" else "sum"
            agg = f"round({fn}(d.{col}), 3)" if fn == "avg" else f"round(sum(d.{col}), 2)" if "Float" in numeric[i]["type"] \
                else f"sum(d.{col})"
        if "status" in colnames and key in MONEY:
            want_status = "refunded" if key == "refunds" else "paid"
            told = "only paid invoices are revenue" in tcomment
            if not told:
                obs = yield Action("tool", tool="run_select_query", args={"query": f"SELECT DISTINCT status FROM analytics.{name}"})
                values = [r[0] for r in (obs.get("result") or {}).get("rows", [])]
                if key == "refunds" and "refunded" in values:
                    flt = "d.status = 'refunded'"
                elif want_status in values and self.u("status") < self.m["status_filter_when_unsure"]:
                    flt = f"d.status = '{want_status}'"
                else:
                    conf *= 0.7
            else:
                flt = f"d.status = '{want_status}'"
        if "event" in colnames and key == "active_accounts":
            told = "'login'" in tcomment
            if told or self.u("event") < 0.5:
                flt = "d.event = 'login'"
            else:
                conf *= 0.6
        return Metric(key or "unknown", name, agg, flt, date), conf


def planner_factory(mcfg: dict, levers_cfg: dict, seed: int):
    def make(qid: str):
        p = SimPlanner(mcfg, seed, qid)
        p.floor = levers_cfg["abstain_below_confidence"]
        p.m_clarify = levers_cfg["clarify_margin"]
        return p
    return make
