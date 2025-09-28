# src/tac/program.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .instructions import Instr

@dataclass
class TacFunction:
    name: str
    params: List[str] = field(default_factory=list)  # nombres lógicos (opcional)
    ret: str = "Void"
    locals_count: int = 0
    code: List[Instr] = field(default_factory=list)

    def __str__(self) -> str:
        header = f".func {self.name}({', '.join(self.params)}) : {self.ret}\n  .locals {self.locals_count}"
        body = "\n".join("  " + str(i) if not str(i).endswith(":") else str(i) for i in self.code)
        return f"{header}\n{body}\n.endfunc"

@dataclass
class TacProgram:
    functions: List[TacFunction] = field(default_factory=list)

    def add(self, fn: TacFunction):
        self.functions.append(fn)

    def dump(self) -> str:
        return "\n\n".join(str(f) for f in self.functions)
