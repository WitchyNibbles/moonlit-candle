"""What a key held before witchy set it, and how to put it back."""
from __future__ import annotations

import copy


def snapshot(container: dict, key: str) -> dict:
    return {"value": copy.deepcopy(container[key])} if key in container else {"absent": True}


def put_back(container: dict, key: str, previous: dict) -> None:
    if previous.get("absent"):
        container.pop(key, None)
    else:
        container[key] = copy.deepcopy(previous["value"])
