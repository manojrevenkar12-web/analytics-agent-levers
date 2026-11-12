"""The person on the other side of a clarifying question. They know what they meant; the agent does not."""

from __future__ import annotations


def responder(truth, platform_cfg: dict, world_cfg: dict):
    def reply(text: str) -> str:
        if text.lower().startswith("which account") and truth.entity:
            return truth.entity
        if truth.metric:
            return platform_cfg["metrics"][truth.metric]["description"]
        return world_cfg["user"]["unknown_reply"].format(term=truth.term)
    return reply
