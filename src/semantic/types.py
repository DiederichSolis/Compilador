from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict

class Type:
    name: str = "<type>"

    def __eq__(self, other):
        return isinstance(other, Type) and self.name == other.name

    def __str__(self):
        return self.name


class IntType(Type):    name = "Int"
class FloatType(Type):  name = "Float"   
class BoolType(Type):   name = "Bool"
class StringType(Type): name = "String"
class NullType(Type):   name = "Null"
class VoidType(Type):   name = "Void"


@dataclass(frozen=True)
class ArrayType(Type):
    elem: Type
    def __str__(self):
        return f"[{self.elem}]"
    @property
    def name(self):
        return f"Array<{self.elem}>"

@dataclass
class ClassType(Type):
    class_name: str
    members: Dict[str, Type]
    def __str__(self):
        return self.class_name
    @property
    def name(self):
        return self.class_name

# Singleton instances
INT    = IntType()
FLOAT  = FloatType()   
BOOL   = BoolType()
STR    = StringType()
NULL   = NullType()
VOID   = VoidType()
