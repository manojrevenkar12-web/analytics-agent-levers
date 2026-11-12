"""Was the outcome right? Compared on result sets, as the person would judge the answer, not on SQL text."""

from __future__ import annotations

import math

OUTCOMES = ("correct", "wrong", "missed", "gave_up")


def _num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def same_rows(got: list | None, want: list | None, rel: float = 0.005) -> bool:
    if got is None or want is None or len(got) != len(want):
        return False
    for g, w in zip(got, want, strict=True):
        if len(g) != len(w):
            return False
        for a, b in zip(g, w, strict=True):
            fa, fb = _num(a), _num(b)
            if fa is not None and fb is not None:
                if not math.isclose(fa, fb, rel_tol=rel, abs_tol=0.01):
                    return False
            elif str(a) != str(b):
                return False
    return True


def judge(outcome, truth) -> str:
    """correct: the right answer, or 'not sure' to an unanswerable question. wrong: an answer that is not right (the
    one that costs trust). missed: 'not sure' when it could have answered. gave_up: ran out of turns."""
    if outcome.kind == "gave_up":
        return "gave_up"
    if truth.kind == "unanswerable":
        return "correct" if outcome.kind == "abstain" else "wrong"
    if outcome.kind == "abstain":
        return "missed"
    return "correct" if same_rows(outcome.rows, truth.answer) else "wrong"
