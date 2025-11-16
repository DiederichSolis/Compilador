# src/backend/mips/generator.py

from __future__ import annotations
from typing import Dict, List, Set, Iterable

from ir.tac.program import TacProgram, TacFunction
from ir.tac import instructions as I

class SimpleRegAllocator:
    """
    Asignador simple de registros temporales.

    No mantiene variables vivas en registros entre instrucciones,
    solo reparte $t0–$t7 de forma cíclica para usarlos como scratch.
    La persistencia sigue estando en el stack (via _store_operand / _load_operand).
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
    Genera MIPS32 (estilo MARS/SPIM) desde un TacProgram.

    Convenciones que usa:
      - Stack frame por función, con stack creciendo hacia abajo.
      - Parámetros se pasan SIEMPRE por stack usando instrucciones TAC `param` + `call`.
      - Layout de frame (al entrar a la función, después del prólogo):

            $sp ---> [ local_0 ]
                     [ local_1 ]
                     ...
                     [ local_K-1 ]
                     [ saved $ra ]
                     [ arg_0 ]
                     [ arg_1 ]
                     ...
                     [ arg_{N-1} ]

        Donde:
          * locals/temporales se guardan desde $sp + 0, +4, ...
          * parámetros se ven desde $sp + locals_size + 4*(i+1)

      - El caller limpia los parámetros de la pila después del `jal`.
      - El callee guarda `ra` y reserva espacio para locales/temporales.
    """

    def __init__(self) -> None:
        # Segmentos
        self.data_lines: List[str] = []
        self.text_lines: List[str] = []

        # Pool de strings: texto -> label
        self.str_pool: Dict[str, str] = {}
        self._str_count: int = 0

        # Estado por función
        self.current_fn: TacFunction | None = None
        self.var_offsets: Dict[str, int] = {}   # %x, t1, etc. -> offset desde $sp
        self.param_offsets: Dict[str, int] = {} # %paramName -> offset desde $sp
        self.locals_size: int = 0               # bytes reservados para locales/temps

        # Estado para llamadas
        self.pending_params: List[str] = []     # operandos TAC de param(...)
        self.fn_end_label: str = ""
        self.need_concat_runtime: bool = False
        self.string_vars: Set[str] = set()
        self.fn_ret_types: Dict[str, str] = {}  # nombre función -> tipo retorno
        self.reg_alloc = SimpleRegAllocator()

    # =====================
    # API pública
    # =====================

    def _is_string_literal_op(self, op: str | None) -> bool:
        return isinstance(op, str) and op.startswith('#"')


    def generate(self, prog: TacProgram) -> str:
        """Genera el texto completo del .s."""
        self.data_lines = []
        self.text_lines = []
        self.str_pool = {}
        self._str_count = 0

        # Cabecera mínima
        self.data_lines.append(".data")
        self.data_lines.append('str_empty: .asciiz ""')
        # Se irán agregando las strings conforme aparezcan

        self.text_lines.append(".text")
        self.text_lines.append(".globl main")
        self.fn_ret_types = {
        fn.name: (fn.ret or "").lower()
        for fn in prog.functions
        }

        for fn in prog.functions:
            self._generate_function(fn)
        if self.need_concat_runtime:
            self._emit_concat_runtime()

        # Agregar strings al .data (después de la línea '.data')
        # Ya fueron empujadas a data_lines a medida que se usaban.
        all_lines = []
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
        """
        Registra una string en el pool y devuelve un label tipo 'str_0'.
        `text` es el contenido literal SIN comillas.
        """
        if text in self.str_pool:
            return self.str_pool[text]
        lbl = f"str_{self._str_count}"
        self._str_count += 1
        # Escape mínimo
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
        """Recolecta todos los operandos de tipo string usados en el código TAC."""
        ops: Set[str] = set()

        def add(op: str | None):
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
                # func suele ser nombre de función, dst es resultado
                add(ins.dst)
            elif isinstance(ins, I.Ret):
                add(ins.value)
            elif isinstance(ins, I.NewObj):
                add(ins.dst)
            elif isinstance(ins, I.GetF):
                add(ins.obj)
                add(ins.dst)
            elif isinstance(ins, I.SetF):
                add(ins.obj)
                add(ins.val)
            elif isinstance(ins, I.NewArr):
                add(ins.size)
                add(ins.dst)
            elif isinstance(ins, I.ALoad):
                add(ins.arr)
                add(ins.idx)
                add(ins.dst)
            elif isinstance(ins, I.AStore):
                add(ins.arr)
                add(ins.idx)
                add(ins.val)
            elif isinstance(ins, I.Print):
                add(ins.arg)
            elif isinstance(ins, I.IfGoto):
                add(ins.cond)
            elif isinstance(ins, I.Goto):
                pass
            elif isinstance(ins, I.Label):
                pass
            else:
                # Por si aparecen instrucciones nuevas, no romper
                for maybe in getattr(ins, "__dict__", {}).values():
                    if isinstance(maybe, str):
                        ops.add(maybe)
        return ops
    
    def _infer_string_vars(self, fn: TacFunction) -> None:
        """
        Marca en self.string_vars los temporales/locals que
        claramente son strings (por venir de literales, concat o toString).
        """
        sv: Set[str] = set()

        for ins in fn.code:
            # x = y
            if isinstance(ins, I.Move) and isinstance(ins.dst, str):
                src = ins.src
                if isinstance(src, str):
                    if self._is_string_literal_op(src) or src in sv:
                        sv.add(ins.dst)

            # x = a + b  (si alguno es string, el resultado también)
            elif isinstance(ins, I.Binary) and ins.op == "+" and isinstance(ins.dst, str):
                a_is_str = isinstance(ins.a, str) and (
                    self._is_string_literal_op(ins.a) or ins.a in sv
                )
                b_is_str = isinstance(ins.b, str) and (
                    self._is_string_literal_op(ins.b) or ins.b in sv
                )
                if a_is_str or b_is_str:
                    sv.add(ins.dst)

            # x = call toString(...)
            elif isinstance(ins, I.Call) and ins.dst and isinstance(ins.dst, str):
                # 1) call toString(...) -> siempre string
                if ins.func == "toString":
                    sv.add(ins.dst)
                else:
                    # 2) cualquier función cuyo TacFunction.ret sea "string"
                    ret_ty = self.fn_ret_types.get(ins.func, "")
                    if ret_ty == "string":
                        sv.add(ins.dst)


        self.string_vars = sv


    def _build_frame(self, fn: TacFunction) -> None:
        """
        Construye:
          - self.var_offsets  (para %locals y tN)
          - self.param_offsets (para %param)
          - self.locals_size
        según la convención descrita en la docstring de la clase.
        """
        self.var_offsets = {}
        self.param_offsets = {}
        self.locals_size = 0

        # %paramName conocidos
        param_ops = {f"%{p}" for p in (fn.params or [])}

        all_ops = self._collect_operands(fn)

        locals_and_temps: List[str] = []
        for op in all_ops:
            if op.startswith("#"):
                continue  # literal
            if op in param_ops:
                continue  # parámetro, se maneja aparte
            if op.startswith("%") or op.startswith("t"):
                locals_and_temps.append(op)

        # Asignar slots a locales + temps
        locals_and_temps = sorted(locals_and_temps)
        for idx, op in enumerate(locals_and_temps):
            self.var_offsets[op] = idx * 4

        self.locals_size = 4 * len(locals_and_temps)

        # Parámetros: %paramName -> offset desde $sp
        # Layout:
        #   [locales ...] (self.locals_size)
        #   [saved $ra]   (+4)
        #   [arg_0]       (+8)
        #   [arg_1]       (+12), etc.
        for i, p in enumerate(fn.params or []):
            name = f"%{p}"
            self.param_offsets[name] = self.locals_size + 4 * (i + 1)

    # =====================
    # Carga/almacenamiento de operandos
    # =====================

    def _is_immediate(self, op: str) -> bool:
        return op.startswith("#")

    def _load_immediate(self, op: str, reg: str) -> None:
        """
        op es tipo: #123, #0, #1, #"texto", #null, ...
        """
        if op.startswith('#"'):
            # String literal
            text = op[2:-1]  # quita #" y la última "
            lbl = self._new_string_label(text)
            self._emit(f"la {reg}, {lbl}")
            return

        val = op[1:]
        if val == "null":
            self._emit(f"li {reg}, 0")
            return
        # bools o ints
        try:
            iv = int(val)
        except ValueError:
            # Si algo raro, pon 0
            self._emit(f"li {reg}, 0")
            return
        self._emit(f"li {reg}, {iv}")

    def _load_operand(self, op: str, reg: str) -> None:
        if self._is_immediate(op):
            self._load_immediate(op, reg)
            return

        # Local/temporal
        if op in self.var_offsets:
            offset = self.var_offsets[op]
            self._emit(f"lw {reg}, {offset}($sp)")
            return

        # Parámetro
        if op in self.param_offsets:
            offset = self.param_offsets[op]
            self._emit(f"lw {reg}, {offset}($sp)")
            return

        # Si no está mapeado (ej. nombre de función), cargar 0
        self._emit(f"li {reg}, 0")

    def _store_operand(self, op: str, reg: str) -> None:
        if op is None:
            return
        if self._is_immediate(op):
            # No tiene sentido guardar en un literal
            return
        if op in self.var_offsets:
            offset = self.var_offsets[op]
            self._emit(f"sw {reg}, {offset}($sp)")
            return
        if op in self.param_offsets:
            offset = self.param_offsets[op]
            self._emit(f"sw {reg}, {offset}($sp)")
            return
        # Si no conocemos el destino, lo ignoramos (podrías loguear)

    # =====================
    # Generación por función
    # =====================

   
    def _emit_concat_runtime(self) -> None:
        """
        Runtime: f_concat(s1: char*, s2: char*) -> char*

        Convención de llamada:
          - El caller (en _emit_binary) hace:
                push s2
                push s1
            por lo que, al entrar a la función:
                0($sp) = s1
                4($sp) = s2

          - Esta función NO modifica $sp.
          - Devuelve en $v0 el puntero al nuevo string.
        """
        self._emit_label("f_concat")

        # Leer parámetros
        self._emit("lw $t0, 0($sp)")   # s1
        self._emit("lw $t1, 4($sp)")   # s2

        # Normalizar nulls -> str_empty
        self._emit("beq $t0, $zero, f_concat_fix_s1")
        self._emit("nop")
        self._emit_label("f_concat_fix_s1_done")

        self._emit("beq $t1, $zero, f_concat_fix_s2")
        self._emit("nop")
        self._emit_label("f_concat_fix_s2_done")

        # len1 en t2
        self._emit("move $t2, $zero")   # len1
        self._emit("move $t3, $t0")     # p = s1
        self._emit_label("f_concat_len1")
        self._emit("lb $t4, 0($t3)")
        self._emit("beq $t4, $zero, f_concat_len1_end")
        self._emit("addiu $t2, $t2, 1")
        self._emit("addiu $t3, $t3, 1")
        self._emit("j f_concat_len1")
        self._emit_label("f_concat_len1_end")

        # len2 en t5
        self._emit("move $t5, $zero")   # len2
        self._emit("move $t3, $t1")     # p = s2
        self._emit_label("f_concat_len2")
        self._emit("lb $t4, 0($t3)")
        self._emit("beq $t4, $zero, f_concat_len2_end")
        self._emit("addiu $t5, $t5, 1")
        self._emit("addiu $t3, $t3, 1")
        self._emit("j f_concat_len2")
        self._emit_label("f_concat_len2_end")

        # total = len1 + len2 + 1
        self._emit("addu $t6, $t2, $t5")
        self._emit("addiu $t6, $t6, 1")

        # sbrk(total)
        self._emit("li $v0, 9")
        self._emit("move $a0, $t6")
        self._emit("syscall")
        self._emit("move $t7, $v0")   # dst base

        # copiar s1 -> dst
        self._emit("move $t3, $t0")   # src = s1
        self._emit("move $t8, $t7")   # dst
        self._emit_label("f_concat_copy1")
        self._emit("lb $t4, 0($t3)")
        self._emit("beq $t4, $zero, f_concat_copy1_end")
        self._emit("sb $t4, 0($t8)")
        self._emit("addiu $t3, $t3, 1")
        self._emit("addiu $t8, $t8, 1")
        self._emit("j f_concat_copy1")
        self._emit_label("f_concat_copy1_end")

        # copiar s2 -> dst
        self._emit("move $t3, $t1")   # src = s2
        self._emit_label("f_concat_copy2")
        self._emit("lb $t4, 0($t3)")
        self._emit("beq $t4, $zero, f_concat_copy2_end")
        self._emit("sb $t4, 0($t8)")
        self._emit("addiu $t3, $t3, 1")
        self._emit("addiu $t8, $t8, 1")
        self._emit("j f_concat_copy2")
        self._emit_label("f_concat_copy2_end")

        # terminador '\0'
        self._emit("sb $zero, 0($t8)")

        # retorno: puntero al nuevo string
        self._emit("move $v0, $t7")
        self._emit("jr $ra")
        self._emit("nop")
        self._emit("")  # línea en blanco

        # Fixups para null: usan str_empty
        self._emit_label("f_concat_fix_s1")
        self._emit("la $t0, str_empty")
        self._emit("j f_concat_fix_s1_done")

        self._emit_label("f_concat_fix_s2")
        self._emit("la $t1, str_empty")
        self._emit("j f_concat_fix_s2_done")




    def _generate_function(self, fn: TacFunction) -> None:
        self.current_fn = fn
        self.pending_params = []
        self.reg_alloc.reset()
        if fn.name in ("printInteger", "printString"):
            self._emit_runtime_print_helper(fn.name)
            # limpiar estado y salir
            self.current_fn = None
            self.pending_params = []
            self.reg_alloc.reset()
            self.var_offsets = {}
            self.param_offsets = {}
            self.locals_size = 0
            return
        
        if fn.name == "toString":  # <-- NUEVO
            self._emit_runtime_to_string()
            self.current_fn = None
            self.pending_params = []
            self.var_offsets = {}
            self.param_offsets = {}
            self.locals_size = 0
            return
        
        self._build_frame(fn)
        self._infer_string_vars(fn)

        # Nombre de label MIPS
        if fn.name == "main":
            label = "main"
        else:
            label = f"f_{fn.name}"

        self.fn_end_label = f"{label}_end"

        # Label de la función
        self._emit_label(label)

        # Prólogo:
        #  1) guardar $ra
        #  2) reservar espacio para locales/temps
        self._emit("addiu $sp, $sp, -4")
        self._emit("sw $ra, 0($sp)")
        if self.locals_size > 0:
            self._emit(f"addiu $sp, $sp, -{self.locals_size}")

        # Cuerpo: recorrer todas las instrucciones
        for ins in fn.code:
            self._emit_instruction(ins)

                # Label de salida (por si Ret hace jump acá)
        self._emit_label(self.fn_end_label)

        # Epílogo
        if fn.name == "main":
            # main NO debe hacer jr $ra, debe terminar el programa
            self._emit("li $v0, 10")   # syscall 10 = exit
            self._emit("syscall")
        else:
            # Funciones normales: restaurar stack y regresar
            if self.locals_size > 0:
                self._emit(f"addiu $sp, $sp, {self.locals_size}")
            self._emit("lw $ra, 0($sp)")
            self._emit("addiu $sp, $sp, 4")
            self._emit("jr $ra")

        self._emit("")  # línea en blanco



        self.current_fn = None
        self.pending_params = []
        self.var_offsets = {}
        self.param_offsets = {}
        self.locals_size = 0
    
    def _emit_runtime_print_helper(self, name: str) -> None:
        """
        Implementación manual de:
        - printInteger(x: int): int
        - printString(s: string): string

        Convención:
        - parámetro viene en 0($sp)
        - NO modifican $sp
        - devuelven el mismo valor que reciben
        """
        label = f"f_{name}"
        self._emit_label(label)

        # arg en t0
        self._emit("lw $t0, 0($sp)")

        if name == "printInteger":
            # print int
            self._emit("move $a0, $t0")
            self._emit("li $v0, 1")
            self._emit("syscall")
        else:  # printString
            # print string
            self._emit("move $a0, $t0")
            self._emit("li $v0, 4")
            self._emit("syscall")

        # valor de retorno = argumento original
        self._emit("move $v0, $t0")
        self._emit("jr $ra")
        self._emit("nop")
        self._emit("")  # línea en blanco

    
    def _emit_runtime_to_string(self) -> None:
        """
        f_toString(x: int) -> char*
        Convención:
        - x viene en 0($sp)
        - retorna puntero en $v0
        - NO toca la pila, solo lee el arg.
        """
        self._emit_label("f_toString")

        # n en $t0
        self._emit("lw $t0, 0($sp)")

        # if n == 0 -> caso especial "0"
        self._emit("beq $t0, $zero, f_toString_zero")
        self._emit("nop")

        # 1) Calcular número de dígitos: len en $t2
        self._emit("move $t1, $t0")      # tmp = n
        self._emit("move $t2, $zero")    # len = 0
        self._emit("li $t3, 10")         # divisor 10

        self._emit_label("f_toString_len_loop")
        self._emit("beq $t1, $zero, f_toString_len_end")
        self._emit("div $t1, $t3")
        self._emit("mflo $t1")           # t1 = t1 / 10
        self._emit("addiu $t2, $t2, 1")  # len++
        self._emit("j f_toString_len_loop")

        self._emit_label("f_toString_len_end")
        # 2) reservar len+1 bytes
        self._emit("addu $t4, $t2, 1")   # t4 = len + 1
        self._emit("li $v0, 9")          # sbrk
        self._emit("move $a0, $t4")
        self._emit("syscall")
        self._emit("move $t6, $v0")      # base
        # puntero de escritura: base + len
        self._emit("addu $t7, $t6, $t2")
        # terminador '\0'
        self._emit("sb $zero, 0($t7)")
        self._emit("addiu $t7, $t7, -1") # ahora apunta al último dígito

        # 3) escribir dígitos de derecha a izquierda
        self._emit("move $t1, $t0")      # n otra vez
        self._emit_label("f_toString_fill_loop")
        self._emit("beq $t2, $zero, f_toString_fill_end")
        self._emit("li $t3, 10")
        self._emit("div $t1, $t3")
        self._emit("mfhi $t4")           # rem = n % 10
        self._emit("mflo $t1")           # n  = n / 10
        self._emit("addiu $t4, $t4, 48") # '0' + rem
        self._emit("sb $t4, 0($t7)")
        self._emit("addiu $t7, $t7, -1")
        self._emit("addiu $t2, $t2, -1")
        self._emit("j f_toString_fill_loop")

        self._emit_label("f_toString_fill_end")
        self._emit("move $v0, $t6")      # return base
        self._emit("jr $ra")
        self._emit("nop")
        self._emit("")  # línea en blanco

        # caso n == 0: construir "0\0"
        self._emit_label("f_toString_zero")
        self._emit("li $v0, 9")
        self._emit("li $a0, 2")          # "0\0"
        self._emit("syscall")
        self._emit("move $t6, $v0")
        self._emit("li $t4, 48")         # '0'
        self._emit("sb $t4, 0($t6)")
        self._emit("sb $zero, 1($t6)")
        self._emit("move $v0, $t6")
        self._emit("jr $ra")
        self._emit("nop")
        self._emit("")  # línea en blanco




    # =====================
    # Instrucciones TAC -> MIPS
    # =====================

    def _emit_instruction(self, ins: I.Instruction) -> None:
        if isinstance(ins, I.Label):
            # Label interno (no el de la función)
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
        elif isinstance(ins, I.NewObj):
            self._emit_newobj(ins)
        elif isinstance(ins, I.GetF):
            self._emit_getf(ins)
        elif isinstance(ins, I.SetF):
            self._emit_setf(ins)
        elif isinstance(ins, I.NewArr):
            self._emit_newarr(ins)
        elif isinstance(ins, I.ALoad):
            self._emit_aload(ins)
        elif isinstance(ins, I.AStore):
            self._emit_astore(ins)
        elif isinstance(ins, I.Print):
            self._emit_print(ins)
        else:
            # Por si hay algo no contemplado
            self._emit(f"# [WARN] instrucción TAC no soportada todavía: {ins}")

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
        op = ins.op

        # --- CASO ESPECIAL: concatenación de strings ---
        if op == "+" and (
            self._is_string_literal_op(ins.a)
            or self._is_string_literal_op(ins.b)
            or (isinstance(ins.a, str) and ins.a in self.string_vars)
            or (isinstance(ins.b, str) and ins.b in self.string_vars)
        ):
            # dst = a + b  ->  llamamos a f_concat(a, b)
            self._load_operand(ins.a, "$t0")  # s1
            self._load_operand(ins.b, "$t1")  # s2

            # push s2, luego s1
            self._emit("addiu $sp, $sp, -4")
            self._emit("sw $t1, 0($sp)")   # s2
            self._emit("addiu $sp, $sp, -4")
            self._emit("sw $t0, 0($sp)")   # s1

            self._emit("jal f_concat")
            self._emit("addiu $sp, $sp, 8")  # limpiar params

            if ins.dst:
                self._store_operand(ins.dst, "$v0")

            self.need_concat_runtime = True
            return

        # --- resto: operaciones aritméticas/lógicas normales (enteros) ---
        self._load_operand(ins.a, ra := self.reg_alloc.get())
        self._load_operand(ins.b, rb := self.reg_alloc.get())
        rd = self.reg_alloc.get()

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
        # Solo recordar el operando; el push real se hace al ver el Call.
        self.pending_params.append(ins.arg)

    def _emit_call(self, ins: I.Call) -> None:
            # Convención:
        #   - params acumulados en self.pending_params, en orden lógico.
        #   - Se pushean en REVERSE (para que arg0 quede más lejos).
        #   - jal fn
        #   - caller limpia la pila.
        args = list(self.pending_params)
        n = len(args)

        # 1) Materializar TODOS los argumentos en registros
        #    mientras $sp está en la base del frame.
        temp_regs = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7"]
        if n > len(temp_regs):
            # Para este proyecto no deberías pasar de 7–8 args;
            # si pasa, mejor que truene explícito.
            raise RuntimeError(f"Demasiados parámetros en llamada a {ins.func}: {n}")

        regs: List[str] = []
        for i, op in enumerate(args):
            r = temp_regs[i]
            self._load_operand(op, r)   # usa $sp base (sin haberlo movido)
            regs.append(r)

        # 2) Pushear en orden reverso para que arg0 quede más lejos
        for r in reversed(regs):
            self._emit("addiu $sp, $sp, -4")
            self._emit(f"sw {r}, 0($sp)")

        # 3) Llamada
        func_name = ins.func
        label = "main" if func_name == "main" else f"f_{func_name}"
        self._emit(f"jal {label}")

        # 4) Limpiar args del stack
        if n > 0:
            self._emit(f"addiu $sp, $sp, {4 * n}")

        # 5) Limpiar estado de params pendientes
        self.pending_params = []

        # 6) Guardar resultado en dst, si lo hay
        if ins.dst:
            self._store_operand(ins.dst, "$v0")


    def _emit_ret(self, ins: I.Ret) -> None:
        # Guardar valor en $v0 (si hay)
        if ins.value:
            self._load_operand(ins.value, "$v0")
        # Saltar al epílogo común
        self._emit(f"j {self.fn_end_label}")

    # --- objetos / campos (muy simplificado) ---

    def _emit_newobj(self, ins: I.NewObj) -> None:
        # sbrk(16)
        self._emit("li $v0, 9")      # syscall sbrk
        self._emit("li $a0, 64")     # 16 bytes arbitrarios
        self._emit("syscall")
        self._store_operand(ins.dst, "$v0")


    def _emit_getf(self, ins: I.GetF) -> None:
        """
        dst = *(obj + field)
        Si obj es null, deja dst = 0 para evitar explotar.
        """
        # Cargar el puntero al objeto en $t0
        self._load_operand(ins.obj, "$t0")

        offset = ins.field   # o ins.offset según tu dataclass

        lbl_null = f"getf_null_{id(ins)}"
        lbl_end  = f"getf_end_{id(ins)}"

        # if (obj == 0) -> dst = 0
        self._emit(f"beq $t0, $zero, {lbl_null}")
        self._emit("nop")  # delay slot seguro
        # normal: leer campo
        self._emit(f"lw $t1, {offset}($t0)")
        self._emit(f"j {lbl_end}")

        # caso null
        self._emit_label(lbl_null)
        self._emit("move $t1, $zero")

        # fin
        self._emit_label(lbl_end)
        self._store_operand(ins.dst, "$t1")


    def _emit_setf(self, ins: I.SetF) -> None:
        """
        *(obj + field) = val
        Si obj es null, no hace nada.
        """
        self._load_operand(ins.obj, "$t0")
        self._load_operand(ins.val, "$t1")

        offset = ins.field   # o ins.offset si así se llama

        lbl_end = f"setf_end_{id(ins)}"

        # if (obj == 0) -> skip write
        self._emit(f"beq $t0, $zero, {lbl_end}")
        self._emit("nop")  # delay slot seguro
        self._emit(f"sw $t1, {offset}($t0)")
        self._emit_label(lbl_end)



    # --- arreglos ---

    def _emit_newarr(self, ins: I.NewArr) -> None:
        """
        newarr elem_ty, size -> dst

        Implementación simple:
          - reserva (size + 1) * 4 bytes
          - en [ptr] guarda size
          - en [ptr + 4*i] los elementos (inicialmente 0)
        """
        # carga size en $t0
        self._load_operand(ins.size, "$t0")

        # bytes = (size + 1) * 4
        self._emit("addiu $t1, $t0, 1")
        self._emit("sll $t1, $t1, 2")  # *4

        # sbrk(bytes)
        self._emit("li $v0, 9")
        self._emit("move $a0, $t1")
        self._emit("syscall")

        # $v0 = ptr
        # guarda size en [ptr]
        self._emit("sw $t0, 0($v0)")

        # dst = ptr
        self._store_operand(ins.dst, "$v0")

    def _emit_aload(self, ins: I.ALoad) -> None:
        # dst = arr[idx]
        self._load_operand(ins.arr, "$t0")  # ptr
        self._load_operand(ins.idx, "$t1")  # idx
        # offset = (idx + 1) * 4
        self._emit("addiu $t1, $t1, 1")
        self._emit("sll $t1, $t1, 2")
        self._emit("addu $t2, $t0, $t1")
        self._emit("lw $t3, 0($t2)")
        self._store_operand(ins.dst, "$t3")

    def _emit_astore(self, ins: I.AStore) -> None:
        # arr[idx] = val
        self._load_operand(ins.arr, "$t0")
        self._load_operand(ins.idx, "$t1")
        self._load_operand(ins.val, "$t2")
        self._emit("addiu $t1, $t1, 1")
        self._emit("sll $t1, $t1, 2")
        self._emit("addu $t3, $t0, $t1")
        self._emit("sw $t2, 0($t3)")

    # --- print ---

    def _emit_print(self, ins: I.Print) -> None:
        op = ins.arg

        # Caso 1: literal de string #"..."
        if isinstance(op, str) and op.startswith('#"'):
            self._load_immediate(op, "$a0")
            self._emit("li $v0, 4")   # print_string
            self._emit("syscall")

        # Caso 2: variable/temporal marcado como string
        elif isinstance(op, str) and op in self.string_vars:
            self._load_operand(op, "$a0")
            self._emit("li $v0, 4")   # print_string
            self._emit("syscall")

        # Caso 3: asumimos entero
        else:
            self._load_operand(op, "$a0")
            self._emit("li $v0, 1")   # print_int
            self._emit("syscall")

        # salto de línea
        self._emit("li $v0, 11")
        self._emit("li $a0, 10")
        self._emit("syscall")



def generate_mips(prog: TacProgram) -> str:
    """
    Helper para usar fácil desde tu main:
        from backend.mips.generator import generate_mips
    """
    gen = MIPSGenerator()
    return gen.generate(prog)