from __future__ import annotations

import copy
from functools import cache

from alv.config import platform, world
from alv.world.warehouse import build


def small_world() -> dict:
    w = copy.deepcopy(world("world"))
    w["warehouse"]["accounts"] = 150
    w["warehouse"]["events_per_account"] = 120
    w["warehouse"]["tickets"] = 3000
    w["questions"]["count"] = 80
    return w


@cache
def session():
    return build(small_world()["warehouse"])


def cfg() -> dict:
    return copy.deepcopy(platform())
