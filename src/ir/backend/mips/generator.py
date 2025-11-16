# src/backend/mips/generator.py

from __future__ import annotations
from typing import Dict, List, Set

from ir.tac.program import TacProgram, TacFunction
from ir.tac import instructions as I


class SimpleRegAllocator:
    """
    Asignador simple de registros temporales.

    No mantiene variables vivas entre instrucciones, solo reparte $t0–$t7
    de forma cíclica como scratch.
    """

    def __init__(self) -> None:
        self.regs = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7"]
        self.idx = 0

    def get(self) -> str:
        r = self.regs[self.idx]
        self.idx = (self.idx + 1) % len(self.regs)
        return r

    def reset(self) -> None:
        self.idx = 0


class MIPSGenerator:
    """
    Versión simplificada del generador de MIPS.

    Soporta:
      - enteros
      - labels, saltos y condicionales
      - aritmética y comparaciones
      - llamadas con parámetros por stack
      - print de enteros y literales de string (#"hola")

    NO soporta:
      - objetos / campos
      - arreglos
      - concatenación de strings
      - toString ni helpers runtime especiales
    """

    def __init__(self) -> None:
        # segmentos
        self.data_lines: List[str] = []
        self.text_lines: List[str] = []

        # pool de strings: contenido -> label
        self.str_pool: Dict[str, str] = {}
        self._str_count: int = 0

        # estado por función
        self.current_fn: TacFunction | None = None
        self.var_offsets: Dict[str, int] = {}   # %x, t1, etc. -> offset desde $sp
        self.param_offsets: Dict[str, int] = {} # %paramName -> offset desde $sp
        self.locals_size: int = 0               # bytes reservados para locales/temps
        self.pending_params: List[str] = []     # operandos TAC de param(...)
        self.fn_end_label: str = ""
        self.reg_alloc = SimpleRegAllocator()

    # =====================
    # API pública
    # =====================

    def generate(self, prog: TacProgram) -> str:
        """Genera el .s completo a partir de un TacProgram."""
        # reset
        self.data_lines = []
        self.text_lines = []
        self.str_pool = {}
        self._str_count = 0

        # .data mínimo
        self.data_lines.append(".data")
        self.data_lines.append('str_empty: .asciiz ""')

        # .text
        self.text_lines.append(".text")
        self.text_lines.append(".globl main")

        for fn in prog.functions:
            self._generate_function(fn)

        all_lines: List[str] = []
        all_lines.extend(self.data_lines)
        all_lines.extend(self.text_lines)
        return "\n".join(all_lines) + "\n"

    # =====================
    # Helpers de emisión
    # =====================

    def _emit(self, line: str) -> None:
        self.text_lines.append("    " + line)

    def _emit_label(self, label: str) -> None:
        self.text_lines.append(f"{label}:")

    def _new_string_label(self, text: str) -> str:
        """Registra una string en el pool y devuelve un label tipo str_0."""
        if text in self.str_pool:
            return self.str_pool[text]
        lbl = f"str_{self._str_count}"
        self._str_count += 1
        escaped = (
            text
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace('"', '\\"')
        )
        self.data_lines.append(f'{lbl}: .asciiz "{escaped}"')
        self.str_pool[text] = lbl
        return lbl

    # =====================
    # Layout de frame
    # =====================

    def _collect_operands(self, fn: TacFunction) -> Set[str]:
        """Recolecta todos los operandos tipo nombre (%x, t0, etc.)."""
        ops: Set[str] = set()

        def add(op: str | None) -> None:
            if isinstance(op, str):
                ops.add(op)

        for ins in fn.code:
            if isinstance(ins, I.Move):
                add(ins.src)
                add(ins.dst)
            elif isinstance(ins, I.Binary):
                add(ins.a)
                add(ins.b)
                add(ins.dst)
            elif isinstance(ins, I.Unary):
                add(ins.a)
                add(ins.dst)
            elif isinstance(ins, I.Param):
                add(ins.arg)
            elif isinstance(ins, I.Call):
                add(ins.dst)
            elif isinstance(ins, I.Ret):
                add(ins.value)
            elif isinstance(ins, I.Print):
                add(ins.arg)
            elif isinstance(ins, I.IfGoto):
                add(ins.cond)
            # Label / Goto no aportan operandos
            # Cualquier otra instrucción la ignoramos en esta versión simple
        return ops

    def _build_frame(self, fn: TacFunction) -> None:
        """
        Construye:
          - var_offsets para locales/temporales
          - param_offsets para parámetros
          - locals_size
        """
        self.var_offsets = {}
        self.param_offsets = {}
        self.locals_size = 0

        param_ops = {f"%{p}" for p in (fn.params or [])}
        all_ops = self._collect_operands(fn)

        locals_and_temps: List[str] = []
        for op in all_ops:
            if op.startswith("#"):
                continue  # literal
            if op in param_ops:
                continue  # parámetro se maneja aparte
            if op.startswith("%") or op.startswith("t"):
                locals_and_temps.append(op)

        locals_and_temps = sorted(locals_and_temps)
        for idx, op in enumerate(locals_and_temps):
            self.var_offsets[op] = idx * 4

        self.locals_size = 4 * len(locals_and_temps)

        # parámetros: %paramName -> offset desde $sp
        # Layout:
        #   [locales ...] (locals_size)
        #   [saved $ra]   (+4)
        #   [arg_0]       (+8)
        #   [arg_1]       (+12), etc.
        for i, p in enumerate(fn.params or []):
            name = f"%{p}"
            self.param_offsets[name] = self.locals_size + 4 * (i + 1)

    # =====================
    # Carga / almacenamiento
    # =====================

    def _is_immediate(self, op: str) -> bool:
        return op.startswith("#")

    def _load_immediate(self, op: str, reg: str) -> None:
        """
        op: #123, #0, #1, #"texto", #null, etc.
        """
        if op.startswith('#"'):
            # literal de string
            text = op[2:-1]  # quita #" y la última "
            lbl = self._new_string_label(text)
            self._emit(f"la {reg}, {lbl}")
            return

        val = op[1:]
        if val == "null":
            self._emit(f"li {reg}, 0")
            return

        try:
            iv = int(val)
        except ValueError:
            self._emit(f"li {reg}, 0")
            return

        self._emit(f"li {reg}, {iv}")

    def _load_operand(self, op: str, reg: str) -> None:
        if self._is_immediate(op):
            self._load_immediate(op, reg)
            return

        if op in self.var_offsets:
            offset = self.var_offsets[op]
            self._emit(f"lw {reg}, {offset}($sp)")
            return

        if op in self.param_offsets:
            offset = self.param_offsets[op]
            self._emit(f"lw {reg}, {offset}($sp)")
            return

        # si no sabemos qué es, carga 0
        self._emit(f"li {reg}, 0")

    def _store_operand(self, op: str | None, reg: str) -> None:
        if op is None:
            return
        if self._is_immediate(op):
            return
        if op in self.var_offsets:
            offset = self.var_offsets[op]
            self._emit(f"sw {reg}, {offset}($sp)")
            return
        if op in self.param_offsets:
            offset = self.param_offsets[op]
            self._emit(f"sw {reg}, {offset}($sp)")
            return
        # destino desconocido: lo ignoramos

    # =====================
    # Funciones
    # =====================

    def _generate_function(self, fn: TacFunction) -> None:
        self.current_fn = fn
        self.pending_params = []
        self.reg_alloc.reset()
        self._build_frame(fn)

        label = "main" if fn.name == "main" else f"f_{fn.name}"
        self.fn_end_label = f"{label}_end"

        # label de la función
        self._emit_label(label)

        # prólogo: guarda $ra y reserva espacio para locales
        self._emit("addiu $sp, $sp, -4")
        self._emit("sw $ra, 0($sp)")
        if self.locals_size > 0:
            self._emit(f"addiu $sp, $sp, -{self.locals_size}")

        # cuerpo
        for ins in fn.code:
            self._emit_instruction(ins)

        # label de salida común (por Ret)
        self._emit_label(self.fn_end_label)

        # epílogo
        if fn.name == "main":
            self._emit("li $v0, 10")   # exit
            self._emit("syscall")
        else:
            if self.locals_size > 0:
                self._emit(f"addiu $sp, $sp, {self.locals_size}")
            self._emit("lw $ra, 0($sp)")
            self._emit("addiu $sp, $sp, 4")
            self._emit("jr $ra")

        self._emit("")  # línea en blanco

        # limpiar estado
        self.current_fn = None
        self.pending_params = []
        self.var_offsets = {}
        self.param_offsets = {}
        self.locals_size = 0

    # =====================
    # Instrucciones TAC -> MIPS
    # =====================

    def _emit_instruction(self, ins: I.Instruction) -> None:
        if isinstance(ins, I.Label):
            self._emit_label(ins.name)
        elif isinstance(ins, I.Goto):
            self._emit(f"j {ins.label}")
        elif isinstance(ins, I.IfGoto):
            self._emit_if_goto(ins)
        elif isinstance(ins, I.Move):
            self._emit_move(ins)
        elif isinstance(ins, I.Binary):
            self._emit_binary(ins)
        elif isinstance(ins, I.Unary):
            self._emit_unary(ins)
        elif isinstance(ins, I.Param):
            self._emit_param(ins)
        elif isinstance(ins, I.Call):
            self._emit_call(ins)
        elif isinstance(ins, I.Ret):
            self._emit_ret(ins)
        elif isinstance(ins, I.Print):
            self._emit_print(ins)
        else:
            # cualquier cosa no soportada la marcamos como comentario
            self._emit(f"# [WARN] TAC no soportado: {ins}")

    # --- if / goto ---

    def _emit_if_goto(self, ins: I.IfGoto) -> None:
        reg = self.reg_alloc.get()
        self._load_operand(ins.cond, reg)
        if ins.sense:
            self._emit(f"bne {reg}, $zero, {ins.label}")
        else:
            self._emit(f"beq {reg}, $zero, {ins.label}")

    # --- move / aritmética / lógica ---

    def _emit_move(self, ins: I.Move) -> None:
        self._load_operand(ins.src, "$t0")
        self._store_operand(ins.dst, "$t0")

    def _emit_binary(self, ins: I.Binary) -> None:
        ra = self.reg_alloc.get()
        rb = self.reg_alloc.get()
        rd = self.reg_alloc.get()

        self._load_operand(ins.a, ra)
        self._load_operand(ins.b, rb)

        op = ins.op

        if op == "+":
            self._emit(f"addu {rd}, {ra}, {rb}")
        elif op == "-":
            self._emit(f"subu {rd}, {ra}, {rb}")
        elif op == "*":
            self._emit(f"mul {rd}, {ra}, {rb}")  # pseudo
        elif op == "/":
            self._emit(f"div {ra}, {rb}")
            self._emit(f"mflo {rd}")
        elif op == "%":
            self._emit(f"div {ra}, {rb}")
            self._emit(f"mfhi {rd}")
        elif op == "==":
            self._emit(f"seq {rd}, {ra}, {rb}")
        elif op == "!=":
            self._emit(f"sne {rd}, {ra}, {rb}")
        elif op == "<":
            self._emit(f"slt {rd}, {ra}, {rb}")
        elif op == "<=":
            self._emit(f"sle {rd}, {ra}, {rb}")
        elif op == ">":
            self._emit(f"sgt {rd}, {ra}, {rb}")
        elif op == ">=":
            self._emit(f"sge {rd}, {ra}, {rb}")
        else:
            self._emit("# op binario desconocido, resultado = 0")
            self._emit(f"li {rd}, 0")

        self._store_operand(ins.dst, rd)

    def _emit_unary(self, ins: I.Unary) -> None:
        src = self.reg_alloc.get()
        dst = self.reg_alloc.get()
        self._load_operand(ins.a, src)

        if ins.op == "-":
            self._emit(f"subu {dst}, $zero, {src}")
        elif ins.op == "!":
            self._emit(f"seq {dst}, {src}, $zero")
        else:
            self._emit("# op unario desconocido, deja el operando igual")
            self._emit(f"move {dst}, {src}")

        self._store_operand(ins.dst, dst)

    # --- llamadas ---

    def _emit_param(self, ins: I.Param) -> None:
        # solo acumulamos, el push se hace en Call
        self.pending_params.append(ins.arg)

    def _emit_call(self, ins: I.Call) -> None:
        """
        Convención:
          - pending_params tiene los args en orden lógico.
          - Cargamos todos los args en registros mientras $sp está "limpio".
          - Luego pusheamos en orden reverso, jal, y limpiamos.
        """
        args = list(self.pending_params)
        n = len(args)

        temp_regs = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7"]
        if n > len(temp_regs):
            raise RuntimeError(f"Demasiados parámetros en llamada a {ins.func}: {n}")

        regs: List[str] = []
        for i, op in enumerate(args):
            r = temp_regs[i]
            self._load_operand(op, r)
            regs.append(r)

        # pushear en reversa
        for r in reversed(regs):
            self._emit("addiu $sp, $sp, -4")
            self._emit(f"sw {r}, 0($sp)")

        # llamada
        func_name = ins.func
        label = "main" if func_name == "main" else f"f_{func_name}"
        self._emit(f"jal {label}")

        # limpiar args
        if n > 0:
            self._emit(f"addiu $sp, $sp, {4 * n}")

        # limpiar estado
        self.pending_params = []

        # guardar retorno
        if ins.dst:
            self._store_operand(ins.dst, "$v0")

    def _emit_ret(self, ins: I.Ret) -> None:
        if ins.value:
            self._load_operand(ins.value, "$v0")
        self._emit(f"j {self.fn_end_label}")

    # --- print ---

    def _emit_print(self, ins: I.Print) -> None:
        op = ins.arg

        # literal de string: #"..."
        if isinstance(op, str) and op.startswith('#"'):
            self._load_immediate(op, "$a0")
            self._emit("li $v0, 4")  # print_string
            self._emit("syscall")
        else:
            # asumimos entero
            self._load_operand(op, "$a0")
            self._emit("li $v0, 1")  # print_int
            self._emit("syscall")

        # salto de línea
        self._emit("li $v0, 11")
        self._emit("li $a0, 10")
        self._emit("syscall")


def generate_mips(prog: TacProgram) -> str:
    """Helper para usar desde tu main."""
    gen = MIPSGenerator()
    return gen.generate(prog)