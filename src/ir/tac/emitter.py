# src/tac/emitter.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from .program import TacFunction
from .instructions import *

@dataclass
class Emitter:
    fn: TacFunction
    temp_counter: int = 0
    label_counter: int = 0

    def t(self) -> str:
        v = f"t{self.temp_counter}"
        self.temp_counter += 1
        return v

    def L(self, base: str="L") -> str:
        v = f"{base}{self.label_counter}"
        self.label_counter += 1
        return v

    def emit(self, instr: Instr) -> Instr:
        self.fn.code.append(instr)
        return instr

    # helpers sugar
    def move(self, src: str, dst: str): self.emit(Move(src, dst))
    def bin(self, op: str, a: str, b: str, dst: str): self.emit(Binary(op, a, b, dst))
    def unary(self, op: str, a: str, dst: str): self.emit(Unary(op, a, dst))
    def label(self, name: str): self.emit(Label(name))
    def goto(self, label: str): self.emit(Goto(label))
    def if_goto(self, cond: str, label: str): self.emit(IfGoto(cond, label, True))
    def if_false(self, cond: str, label: str): self.emit(IfGoto(cond, label, False))
    def param(self, arg: str): self.emit(Param(arg))
    def call(self, f: str, argc: int, dst: str|None): self.emit(Call(f, argc, dst))
    def ret(self, v: str|None=None): self.emit(Ret(v))
    # objetos/arrays/IO
    def new(self, cls: str, dst: str): self.emit(NewObj(cls, dst))
    def getf(self, obj: str, field: str, dst: str): self.emit(GetF(obj, field, dst))
    def setf(self, obj: str, field: str, val: str): self.emit(SetF(obj, field, val))
    def newarr(self, elem_t: str, size: str, dst: str): self.emit(NewArr(elem_t, size, dst))
    def aload(self, arr: str, idx: str, dst: str): self.emit(ALoad(arr, idx, dst))
    def astore(self, arr: str, idx: str, val: str): self.emit(AStore(arr, idx, val))
    def print(self, arg: str): self.emit(Print(arg))
    def last_is_terminal(self) -> bool:
        if not self.fn.code:
            return False
        from .instructions import Goto, Ret
        last = self.fn.code[-1]
        return isinstance(last, (Goto, Ret))

