"""What a key held before witchy set it, how to set it, and how to put it back."""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping


def snapshot(container: dict, key: str) -> dict:
    return {"value": copy.deepcopy(container[key])} if key in container else {"absent": True}


def put_back(container: dict, key: str, previous: dict) -> None:
    if previous.get("absent"):
        container.pop(key, None)
    else:
        container[key] = copy.deepcopy(previous["value"])


def is_installed(container: dict, key: str, record: dict, also: Iterable[Any] = ()) -> bool:
    """Whether ``key`` still holds what witchy installed, or one of ``also`` (other values that count as witchy's)."""
    current = snapshot(container, key)
    return any(current == {"value": value} for value in (record["installed"], *also))


def apply_keys(data: dict, desired: Mapping[str, Any], recorded: dict | None) -> tuple[dict, dict]:
    """Set every desired key. On a reinstall the first-ever previous value is kept, not witchy's own.

    A key that already holds an equal value is left as it is, so a file is never rewritten just to
    reorder an object's members.
    """
    result = copy.deepcopy(data)
    records = {}
    for key, value in desired.items():
        earlier = (recorded or {}).get(key)
        previous = earlier["previous"] if earlier else snapshot(result, key)
        records[key] = {"previous": previous, "installed": copy.deepcopy(value)}
        if snapshot(result, key) != {"value": value}:
            result[key] = copy.deepcopy(value)
    return result, records


def restore_keys(data: dict, records: dict,
                 also_installed: Mapping[str, Iterable[Any]] | None = None) -> tuple[dict, list[str]]:
    """Give back each key's previous value, unless it no longer holds what witchy installed."""
    result = copy.deepcopy(data)
    warnings = []
    for key, record in records.items():
        if snapshot(result, key) == record["previous"]:
            continue  # already given back, for example by an uninstall that stopped part-way
        if not is_installed(result, key, record, (also_installed or {}).get(key, ())):
            warnings.append(f"{key} was changed after install; leaving it as it is.")
            continue
        put_back(result, key, record["previous"])
    return result, warnings
