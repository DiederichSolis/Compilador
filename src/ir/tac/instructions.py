# src/tac/instructions.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Any

# Operandos: temporales t0, locales %x, globales @g, literales #5, #"hola"
Operand = str

@dataclass
class Instr:
    op: str

    def __str__(self) -> str:  # fallback
        return self.op

@dataclass
class Label(Instr):
    name: str
    def __init__(self, name: str): super().__init__("label"); self.name = name
    def __str__(self): return f"{self.name}:"

@dataclass
class Unary(Instr):
    dst: Operand; a: Operand
    def __init__(self, op: str, a: Operand, dst: Operand):
        super().__init__(op); self.a=a; self.dst=dst
    def __str__(self): return f"{self.dst} = {self.op} {self.a}"

@dataclass
class Binary(Instr):
    dst: Operand; a: Operand; b: Operand
    def __init__(self, op: str, a: Operand, b: Operand, dst: Operand):
        super().__init__(op); self.a=a; self.b=b; self.dst=dst
    def __str__(self): return f"{self.dst} = {self.a} {self.op} {self.b}"

@dataclass
class Move(Instr):
    src: Operand; dst: Operand
    def __init__(self, src: Operand, dst: Operand):
        super().__init__("move"); self.src=src; self.dst=dst
    def __str__(self): return f"{self.dst} = {self.src}"

@dataclass
class Goto(Instr):
    label: str
    def __init__(self, label: str): super().__init__("goto"); self.label=label
    def __str__(self): return f"goto {self.label}"

@dataclass
class IfGoto(Instr):
    cond: Operand; label: str; sense: bool=True
    def __init__(self, cond: Operand, label: str, sense: bool=True):
        super().__init__("if"); self.cond=cond; self.label=label; self.sense=sense
    def __str__(self):
        return f"{'if' if self.sense else 'ifFalse'} {self.cond} goto {self.label}"

@dataclass
class Param(Instr):
    arg: Operand
    def __init__(self, arg: Operand): super().__init__("param"); self.arg=arg
    def __str__(self): return f"param {self.arg}"

@dataclass
class Call(Instr):
    func: str; argc: int; dst: Optional[Operand]
    def __init__(self, func: str, argc: int, dst: Optional[Operand]=None):
        super().__init__("call"); self.func=func; self.argc=argc; self.dst=dst
    def __str__(self):
        return f"call {self.func}, {self.argc} -> {self.dst}" if self.dst else f"call {self.func}, {self.argc}"

@dataclass
class Ret(Instr):
    value: Optional[Operand]=None
    def __init__(self, value: Optional[Operand]=None): super().__init__("ret"); self.value=value
    def __str__(self): return f"ret {self.value}" if self.value else "ret"

# Objetos / arrays / IO
@dataclass
class NewObj(Instr):
    cls: str; dst: Operand
    def __init__(self, cls: str, dst: Operand): super().__init__("new"); self.cls=cls; self.dst=dst
    def __str__(self): return f"{self.dst} = new {self.cls}"

@dataclass
class GetF(Instr):
    obj: Operand; field: str; dst: Operand
    def __init__(self, obj: Operand, field: str, dst: Operand):
        super().__init__("getf"); self.obj=obj; self.field=field; self.dst=dst
    def __str__(self): return f"{self.dst} = getf {self.obj}, \"{self.field}\""

@dataclass
class SetF(Instr):
    obj: Operand; field: str; val: Operand
    def __init__(self, obj: Operand, field: str, val: Operand):
        super().__init__("setf"); self.obj=obj; self.field=field; self.val=val
    def __str__(self): return f"setf {self.obj}, \"{self.field}\", {self.val}"

@dataclass
class NewArr(Instr):
    elem_t: str; size: Operand; dst: Operand
    def __init__(self, elem_t: str, size: Operand, dst: Operand):
        super().__init__("newarr"); self.elem_t=elem_t; self.size=size; self.dst=dst
    def __str__(self): return f"{self.dst} = newarr {self.elem_t}, {self.size}"

@dataclass
class ALoad(Instr):
    arr: Operand; idx: Operand; dst: Operand
    def __init__(self, arr: Operand, idx: Operand, dst: Operand):
        super().__init__("aload"); self.arr=arr; self.idx=idx; self.dst=dst
    def __str__(self): return f"{self.dst} = aload {self.arr}, {self.idx}"

@dataclass
class AStore(Instr):
    arr: Operand; idx: Operand; val: Operand
    def __init__(self, arr: Operand, idx: Operand, val: Operand):
        super().__init__("astore"); self.arr=arr; self.idx=idx; self.val=val
    def __str__(self): return f"astore {self.arr}, {self.idx}, {self.val}"

@dataclass
class Print(Instr):
    arg: Operand
    def __init__(self, arg: Operand): super().__init__("print"); self.arg=arg
    def __str__(self): return f"print {self.arg}"
