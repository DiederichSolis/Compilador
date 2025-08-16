# src/semantic/symbols.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .types import Type

@dataclass
class Symbol:
    name: str
    type: Type
    # 'kind' no debe romper el orden de argumentos; lo dejamos con default y fuera de __init__
    kind: str = field(default="", init=False)

@dataclass
class VariableSymbol(Symbol):
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
    kind: str = field(default="class", init=False)
