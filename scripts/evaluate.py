"""Every lever setting on the tuning questions; writes reports/evaluation.json and says which levers ship."""

from __future__ import annotations

import json
import sys
import time

from alv.config import ROOT, platform, world
from alv.evals.compare import evaluate


def main() -> int:
    cfg = platform()
    t = time.time()
    rep = evaluate(world("world"), cfg, cfg["eval"]["seeds"])
    rep["seconds"] = round(time.time() - t, 1)
    (ROOT / "reports" / "evaluation.json").write_text(json.dumps(rep, indent=1) + "\n")
    for name, s in rep["summary"].items():
        print(f"{name:28s} correct {s['correct']:.3f}  wrong {s['wrong']:.3f}  missed {s['missed']:.3f}  "
              f"asked/100 {s['asked_per_100']:4.0f}  ${s['usd_per_question']:.4f}")
    for name, g in rep["gate"].items():
        c = g["correct"]
        print(f"{'SHIP' if g['ship'] else 'hold'} {name:26s} correct {c['diff']:+.3f} [{c['lo']:+.3f}, {c['hi']:+.3f}]")
    print(f"done in {rep['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
