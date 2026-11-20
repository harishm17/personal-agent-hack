"""Owned, sourced memory: the agent remembers only what a real record proves, and every memory has an owner.

`recall(sheet)` is what the engine calls at a reset or a switch of sheet. `write(memory)` is the only way to add
a memory and refuses anything no record proves. Nothing a model reads or writes becomes a memory.
"""
from signoff.memory.recalling import recall
from signoff.memory.sources import Refused
from signoff.memory.store import read, sync, write

__all__ = ["recall", "write", "sync", "read", "Refused"]
