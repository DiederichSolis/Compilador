#program.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .instructions import Instr

@dataclass
class TacFunction:
    name: str
    params: List[str] = field(default_factory=list)
    ret: str = "Void"
    locals_count: int = 0
    code: List[Instr] = field(default_factory=list)

    # --- NUEVO: layout de frame ---
    word: int = 4
    frame: dict[str, dict] = field(default_factory=dict)  # name -> {base, offset, kind}
    _locals_declared: List[str] = field(default_factory=list)

    def alloc_local(self, name: str):
        if name not in self._locals_declared:
            self._locals_declared.append(name)

    def finalize_frame(self):
        # Parámetros: FP + 8 + i*word   (retaddr=4, oldFP=4)
        for i, p in enumerate(self.params):
            self.frame[p] = {"base": "FP", "offset": 8 + i * self.word, "kind": "param"}
        # Locales: FP - word*(i+1)
        for i, v in enumerate(self._locals_declared):
            self.frame[v] = {"base": "FP", "offset": -(i + 1) * self.word, "kind": "local"}

    # Render con o sin direcciones (llamado por TacProgram.dump)
    def to_string(self, debug_addrs: bool = False) -> str:
        header = f".func {self.name}({', '.join(self.params)}) : {self.ret}\n  .locals {self.locals_count}"
        if debug_addrs and self.frame:
            for n, m in self.frame.items():
                header += f"\n  .addr {n} = {m['base']}{m['offset']:+d}  ; {m['kind']}"
        body = "\n".join("  " + str(i) if not str(i).endswith(":") else str(i) for i in self.code)
        return f"{header}\n{body}\n.endfunc"

@dataclass
class TacProgram:
    functions: List[TacFunction] = field(default_factory=list)

    def add(self, fn: TacFunction):
        self.functions.append(fn)

    def get_optimized(self):
        """
        Retorna una copia optimizada del programa TAC
        """
        from .opt.optimizer import TacOptimizer
        optimizer = TacOptimizer()
        import copy
        program = copy.deepcopy(self)
        return optimizer.optimize(program)

    def dump(self, debug_addrs: bool = False, optimize: bool = True) -> str:
        """
        Genera el código TAC como string
        
        Args:
            debug_addrs: Si incluir información de direcciones de memoria
            optimize: Si aplicar optimizaciones antes de generar el código
        """
        program = self
        if optimize:
            from .opt.optimizer import TacOptimizer
            optimizer = TacOptimizer()
            # Crear una copia para no modificar el original
            import copy
            program = copy.deepcopy(self)
            program = optimizer.optimize(program)
        
        return "\n\n".join(f.to_string(debug_addrs=debug_addrs) for f in program.functions)