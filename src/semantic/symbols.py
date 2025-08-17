# src/semantic/symbols.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .types import Type

@dataclass
class Symbol:
    name: str
    type: Type
    # Evitamos problemas de orden en dataclasses
    kind: str = field(default="", init=False)

@dataclass
class VariableSymbol(Symbol):
    is_const: bool = False            # para bloquear reasignación de const
    kind: str = field(default="var", init=False)

@dataclass
class ParamSymbol(Symbol):
    kind: str = field(default="param", init=False)

@dataclass
class FunctionSymbol(Symbol):
    params: List[ParamSymbol] = field(default_factory=list)
    kind: str = field(default="func", init=False)

@dataclass
class ClassSymbol(Symbol):
    fields: Dict[str, Symbol] = field(default_factory=dict)
    methods: Dict[str, FunctionSymbol] = field(default_factory=dict)
    parent: Optional["ClassSymbol"] = field(default=None, repr=False)  # herencia opcional
    kind: str = field(default="class", init=False)
