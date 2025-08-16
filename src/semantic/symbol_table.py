# src/semantic/symbol_table.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from .symbols import Symbol

ScopeKind = str  # 'GLOBAL' | 'FUNCTION' | 'CLASS' | 'BLOCK'

@dataclass
class Scope:
    kind: ScopeKind
    name: str = ""
    parent: Optional["Scope"] = None
    symbols: Dict[str, Symbol] = field(default_factory=dict)

    def define(self, sym: Symbol):
        if sym.name in self.symbols:
            raise KeyError(f"Symbol '{sym.name}' already defined in this scope")
        self.symbols[sym.name] = sym

    def resolve(self, name: str) -> Optional[Symbol]:
        cur: Optional[Scope] = self
        while cur:
            if name in cur.symbols:
                return cur.symbols[name]
            cur = cur.parent
        return None

class SymbolTable:
    def __init__(self):
        self._stack: List[Scope] = [Scope(kind="GLOBAL", name="__global__")]

    @property
    def current(self) -> Scope:
        return self._stack[-1]

    def push(self, kind: ScopeKind, name: str = "") -> Scope:
        scope = Scope(kind=kind, name=name, parent=self.current)
        self._stack.append(scope)
        return scope

    def pop(self) -> Scope:
        if len(self._stack) == 1:
            raise RuntimeError("Cannot pop global scope")
        return self._stack.pop()

    def dump(self) -> list:
        # Para el IDE: devuelve scopes en orden de creación
        out = []
        for s in self._stack:
            out.append({
                "scope": f"{s.kind} {s.name}".strip(),
                "entries": [
                    {"name": k, "kind": v.kind, "type": str(v.type)}
                    for k, v in s.symbols.items()
                ],
            })
        return out
