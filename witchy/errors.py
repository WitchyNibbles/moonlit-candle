"""Exceptions shared by the runner and the components."""
from __future__ import annotations


class Abort(Exception):
    """Stop before anything is written; the message says why."""


class ComponentFailed(Exception):
    """A component could not finish; the message is the reason recorded in state."""
