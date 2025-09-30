from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

class Type:
    @property
    def name(self) -> str:
        return self.__class__.__name__
    def __str__(self) -> str:
        return self.name

class IntType(Type): pass
class FloatType(Type): pass

class BoolType(Type): pass
class StringType(Type): pass
class NullType(Type): pass
class VoidType(Type): pass

@dataclass(frozen=True)
class ArrayType(Type):
    elem: Type
    @property
    def name(self) -> str:
        return f"{self.elem}[]"

@dataclass
class ClassType(Type):
    class_name: str
    members: Dict[str, Type]
    @property
    def name(self) -> str:
        return self.class_name
    def __str__(self) -> str:
        return self.class_name

# singletons útiles
INT   = IntType()
FLOAT = FloatType()
BOOL  = BoolType()
STR   = StringType()
NULL  = NullType()
VOID  = VoidType()