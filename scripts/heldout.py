"""The held-out company: other data, other accounts, words nobody tuned for. Run once.

    python scripts/heldout.py --lock   # record what will be judged: settings (parsed) and code, by hash
    python scripts/heldout.py          # run it once; refuses if anything changed since the lock or it already ran
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import tomllib
from datetime import UTC, datetime

from alv.config import ROOT, platform, world
from alv.evals.compare import evaluate

LOCK = ROOT / "reports" / "heldout.lock"
OUT = ROOT / "reports" / "heldout.json"


def fingerprint() -> str:
    h = hashlib.sha256()
    for name in ("platform.toml", "world_heldout.toml", "descriptions.toml"):
        h.update(name.encode())
        h.update(json.dumps(tomllib.loads((ROOT / "config" / name).read_text()), sort_keys=True).encode())
    for f in sorted((ROOT / "src" / "alv").rglob("*.py")):
        h.update(str(f.relative_to(ROOT)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", action="store_true")
    a = ap.parse_args()
    if OUT.exists():
        print("the held-out company already ran; its result is reports/heldout.json", file=sys.stderr)
        return 1
    if a.lock:
        LOCK.write_text(json.dumps({"fingerprint": fingerprint(), "locked_at": datetime.now(UTC).isoformat()}, indent=1) + "\n")
        print("locked")
        return 0
    if not LOCK.exists() or json.loads(LOCK.read_text())["fingerprint"] != fingerprint():
        print("lock first, and change nothing after locking", file=sys.stderr)
        return 1
    cfg = platform()
    t = time.time()
    rep = evaluate(world("world_heldout"), cfg, [cfg["eval"]["heldout_seed"]], workers=1)
    rep["seconds"], rep["ran_at"] = round(time.time() - t, 1), datetime.now(UTC).isoformat()
    OUT.write_text(json.dumps(rep, indent=1) + "\n")
    for name, g in rep["gate"].items():
        print(f"{'SHIP' if g['ship'] else 'hold'} {name:26s} correct {g['correct']['diff']:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
