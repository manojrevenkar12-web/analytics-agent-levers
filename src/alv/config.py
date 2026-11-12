"""Settings from config/. The product reads platform.toml; only the world, evals and scripts read world*.toml."""

from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path

ROOT = Path(os.environ.get("ALV_ROOT", Path(__file__).resolve().parents[2]))


@cache
def platform() -> dict:
    return tomllib.loads((ROOT / "config" / "platform.toml").read_text(encoding="utf-8"))


def world(name: str = "world") -> dict:
    return tomllib.loads((ROOT / "config" / f"{name}.toml").read_text(encoding="utf-8"))
