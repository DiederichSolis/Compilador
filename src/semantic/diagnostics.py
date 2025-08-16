# src/semantic/diagnostics.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

@dataclass
class Diagnostic:
    phase: str      # 'semantic' | 'syntax'
    code: str       # E001, E101, ...
    message: str
    line: int
    col: int
    extra: Dict[str, Any]

    def to_dict(self):
        return asdict(self)

class Diagnostics:
    def __init__(self):
        self._items: List[Diagnostic] = []

    def add(self, *, phase: str, code: str, message: str, line: int, col: int, **extra):
        self._items.append(Diagnostic(phase=phase, code=code, message=message, line=line, col=col, extra=extra))

    def extend(self, ds: "Diagnostics"):
        self._items.extend(ds._items)

    def empty(self) -> bool:
        return not self._items

    def to_list(self) -> List[dict]:
        return [d.to_dict() for d in self._items]
