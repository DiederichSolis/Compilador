#optimizer
"""
Optimizaciones para código TAC (Three Address Code)
"""

from typing import List, Dict, Set, Optional, Union
from dataclasses import dataclass
from ..instructions import *
from ..program import TacFunction, TacProgram

@dataclass
class OptimizationPass:
    """Clase base para pases de optimización"""
    
    def optimize_function(self, func: TacFunction) -> TacFunction:
        """Optimiza una función individual"""
        raise NotImplementedError
    
    def optimize_program(self, program: TacProgram) -> TacProgram:
        """Optimiza todo el programa"""
        for func in program.functions:
            self.optimize_function(func)
        return program

class TempEliminationPass(OptimizationPass):
    """
    Elimina temporales redundantes del tipo:
    t0 = t1 → reemplaza todos los usos de t0 con t1
    t2 = #5 → reemplaza todos los usos de t2 con #5 (propagación de constantes)
    """
    
    def optimize_function(self, func: TacFunction) -> TacFunction:
        if not func.code:
            return func
            
        # Múltiples pasadas para mejorar optimización
        optimized = True
        passes = 0
        max_passes = 10  # Límite aumentado para mejor optimización
        
        while optimized and passes < max_passes:
            optimized = False
            passes += 1
            
            # Diccionario de reemplazos: temp -> valor_real
            replacements: Dict[str, str] = {}
            new_code: List[Instr] = []
            
            for instr in func.code:
                # Aplicar reemplazos a la instrucción actual
                optimized_instr = self._apply_replacements(instr, replacements)
                
                # Detectar nuevos reemplazos
                if isinstance(optimized_instr, Move):
                    src, dst = optimized_instr.src, optimized_instr.dst
                    
                    # Si es una copia directa de temporal a temporal: t0 = t1
                    if self._is_temp(dst) and (self._is_temp(src) or self._is_literal(src) or self._is_var(src)):
                        replacements[dst] = src
                        optimized = True
                        # No agregamos la instrucción move redundante
                        continue
                        
                # Si no es un move redundante, agregar la instrucción optimizada
                new_code.append(optimized_instr)
            
            # Actualizar el código de la función
            func.code = new_code
        
        return func
    
    def _apply_replacements(self, instr: Instr, replacements: Dict[str, str]) -> Instr:
        """Aplica los reemplazos a una instrucción"""
        
        def replace_operand(operand: str) -> str:
            return replacements.get(operand, operand)
        
        if isinstance(instr, Move):
            return Move(replace_operand(instr.src), replace_operand(instr.dst))
        
        elif isinstance(instr, Binary):
            return Binary(
                instr.op, 
                replace_operand(instr.a), 
                replace_operand(instr.b), 
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, Unary):
            return Unary(
                instr.op,
                replace_operand(instr.a),
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, IfGoto):
            return IfGoto(
                replace_operand(instr.cond),
                instr.label,
                instr.sense
            )
        
        elif isinstance(instr, Param):
            return Param(replace_operand(instr.arg))
        
        elif isinstance(instr, Call):
            return Call(
                replace_operand(instr.func),
                instr.argc,
                replace_operand(instr.dst) if instr.dst else None
            )
        
        elif isinstance(instr, Ret):
            return Ret(replace_operand(instr.value) if instr.value else None)
        
        elif isinstance(instr, NewObj):
            return NewObj(
                replace_operand(instr.cls),
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, GetF):
            return GetF(
                replace_operand(instr.obj),
                instr.field,
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, SetF):
            return SetF(
                replace_operand(instr.obj),
                instr.field,
                replace_operand(instr.val)
            )
        
        elif isinstance(instr, NewArr):
            return NewArr(
                replace_operand(instr.elem_t),
                replace_operand(instr.size),
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, ALoad):
            return ALoad(
                replace_operand(instr.arr),
                replace_operand(instr.idx),
                replace_operand(instr.dst)
            )
        
        elif isinstance(instr, AStore):
            return AStore(
                replace_operand(instr.arr),
                replace_operand(instr.idx),
                replace_operand(instr.val)
            )
        
        elif isinstance(instr, Print):
            return Print(replace_operand(instr.arg))
        
        # Para etiquetas, gotos, etc. que no tienen operandos
        return instr
    
    def _is_temp(self, operand: str) -> bool:
        """Verifica si un operando es un temporal (tN)"""
        return operand.startswith('t') and operand[1:].isdigit()
    
    def _is_literal(self, operand: str) -> bool:
        """Verifica si un operando es un literal (#...)"""
        return operand.startswith('#')
    
    def _is_var(self, operand: str) -> bool:
        """Verifica si un operando es una variable (%var)"""
        return operand.startswith('%')

class DeadCodeEliminationPass(OptimizationPass):
    """
    Elimina código muerto: instrucciones que asignan a variables que nunca se usan
    """
    
    def optimize_function(self, func: TacFunction) -> TacFunction:
        if not func.code:
            return func
        
        # Análisis de uso: qué variables/temporales son usados
        used_vars = self._find_used_variables(func.code)
        
        # Filtrar instrucciones que asignan a variables no usadas
        new_code = []
        for instr in func.code:
            if self._is_dead_assignment(instr, used_vars):
                continue
            new_code.append(instr)
        
        func.code = new_code
        return func
    
    def _find_used_variables(self, code: List[Instr]) -> Set[str]:
        """Encuentra todas las variables/temporales que son usados"""
        used = set()
        
        for instr in code:
            # Agregar variables que son leídas
            if isinstance(instr, Move):
                used.add(instr.src)
            elif isinstance(instr, Binary):
                used.add(instr.a)
                used.add(instr.b)
            elif isinstance(instr, Unary):
                used.add(instr.a)
            elif isinstance(instr, IfGoto):
                used.add(instr.cond)
            elif isinstance(instr, Param):
                used.add(instr.arg)
            elif isinstance(instr, Call):
                used.add(instr.func)
            elif isinstance(instr, Ret) and instr.value:
                used.add(instr.value)
            elif isinstance(instr, GetF):
                used.add(instr.obj)
            elif isinstance(instr, SetF):
                used.add(instr.obj)
                used.add(instr.val)
            elif isinstance(instr, NewArr):
                used.add(instr.elem_t)
                used.add(instr.size)
            elif isinstance(instr, ALoad):
                used.add(instr.arr)
                used.add(instr.idx)
            elif isinstance(instr, AStore):
                used.add(instr.arr)
                used.add(instr.idx)
                used.add(instr.val)
            elif isinstance(instr, Print):
                used.add(instr.arg)
        
        return used
    
    def _is_dead_assignment(self, instr: Instr, used_vars: Set[str]) -> bool:
        """Verifica si una instrucción es una asignación muerta"""
        
        # Solo consideramos asignaciones a temporales
        def assigns_to_unused_temp(dst: str) -> bool:
            return (dst.startswith('t') and dst[1:].isdigit() and 
                   dst not in used_vars)
        
        if isinstance(instr, Move):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, Binary):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, Unary):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, Call) and instr.dst:
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, NewObj):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, GetF):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, NewArr):
            return assigns_to_unused_temp(instr.dst)
        elif isinstance(instr, ALoad):
            return assigns_to_unused_temp(instr.dst)
            
        return False

class PeepholeOptimizationPass(OptimizationPass):
    """
    Optimizaciones peephole: patrones específicos de instrucciones consecutivas
    """
    
    def optimize_function(self, func: TacFunction) -> TacFunction:
        if not func.code:
            return func
        
        code = func.code
        optimized = True
        
        # Iteramos hasta que no haya más optimizaciones
        while optimized:
            new_code, optimized = self._peephole_pass(code)
            code = new_code
        
        func.code = code
        return func
    
    def _peephole_pass(self, code: List[Instr]) -> tuple[List[Instr], bool]:
        """Un pase de optimización peephole"""
        new_code = []
        optimized = False
        i = 0
        
        while i < len(code):
            curr = code[i]
            
            # Patrón: goto L; L: -> eliminar goto
            if (isinstance(curr, Goto) and i + 1 < len(code) and
                isinstance(code[i + 1], Label) and 
                curr.label == code[i + 1].name):
                # Saltar el goto
                optimized = True
                i += 1
                continue
            
            # Patrón: t0 = a + b; t1 = t0; -> t1 = a + b
            if (isinstance(curr, Binary) and i + 1 < len(code) and
                isinstance(code[i + 1], Move) and
                code[i + 1].src == curr.dst and
                self._is_temp(curr.dst)):
                # Combinar las instrucciones
                new_instr = Binary(curr.op, curr.a, curr.b, code[i + 1].dst)
                new_code.append(new_instr)
                optimized = True
                i += 2
                continue
            
            # Patrón similar para unary
            if (isinstance(curr, Unary) and i + 1 < len(code) and
                isinstance(code[i + 1], Move) and
                code[i + 1].src == curr.dst and
                self._is_temp(curr.dst)):
                new_instr = Unary(curr.op, curr.a, code[i + 1].dst)
                new_code.append(new_instr)
                optimized = True
                i += 2
                continue
            
            # Patrón: t0 = call f(...); %var = t0; -> call f(...) -> %var
            if (isinstance(curr, Call) and curr.dst and i + 1 < len(code) and
                isinstance(code[i + 1], Move) and
                code[i + 1].src == curr.dst and
                self._is_temp(curr.dst)):
                new_instr = Call(curr.func, curr.argc, code[i + 1].dst)
                new_code.append(new_instr)
                optimized = True
                i += 2
                continue
            
            # Patrón complejo: t0 = new Class; param t0; ...; call Constructor; %var = t0
            # Buscar patrón extendido de constructor
            if (isinstance(curr, NewObj) and self._is_temp(curr.dst)):
                # Buscar el move final que asigna el temporal a una variable
                constructor_end = -1
                for j in range(i + 1, min(i + 10, len(code))):  # Buscar en las próximas 10 instrucciones
                    if (isinstance(code[j], Move) and 
                        code[j].src == curr.dst and 
                        not self._is_temp(code[j].dst)):
                        constructor_end = j
                        break
                
                if constructor_end != -1:
                    # Cambiar el destino del new
                    new_instr = NewObj(curr.cls, code[constructor_end].dst)
                    new_code.append(new_instr)
                    
                    # Copiar las instrucciones intermedias, reemplazando el temporal
                    for k in range(i + 1, constructor_end):
                        instr = code[k]
                        if isinstance(instr, Param) and instr.arg == curr.dst:
                            # Cambiar param t0 -> param %var
                            new_code.append(Param(code[constructor_end].dst))
                        else:
                            new_code.append(instr)
                    
                    # Saltar todas las instrucciones procesadas
                    optimized = True
                    i = constructor_end + 1
                    continue
            
            # Patrón simple: t0 = new Class; %var = t0; -> %var = new Class
            if (isinstance(curr, NewObj) and i + 1 < len(code) and
                isinstance(code[i + 1], Move) and
                code[i + 1].src == curr.dst and
                self._is_temp(curr.dst)):
                new_instr = NewObj(curr.cls, code[i + 1].dst)
                new_code.append(new_instr)
                optimized = True
                i += 2
                continue
                
            new_code.append(curr)
            i += 1
        
        return new_code, optimized
    
    def _is_temp(self, operand: str) -> bool:
        """Verifica si un operando es un temporal (tN)"""
        return operand.startswith('t') and operand[1:].isdigit()

class ConstantFoldingPass(OptimizationPass):
    """
    Plegado de constantes: evalúa operaciones con constantes en tiempo de compilación
    """
    
    def optimize_function(self, func: TacFunction) -> TacFunction:
        if not func.code:
            return func
        
        new_code = []
        for instr in func.code:
            if isinstance(instr, Binary):
                # Solo trabajamos con literales numéricos
                if (self._is_numeric_literal(instr.a) and 
                    self._is_numeric_literal(instr.b)):
                    result = self._evaluate_binary(instr.op, instr.a, instr.b)
                    if result is not None:
                        # Reemplazar por una asignación simple
                        new_code.append(Move(result, instr.dst))
                        continue
            
            new_code.append(instr)
        
        func.code = new_code
        return func
    
    def _is_numeric_literal(self, operand: str) -> bool:
        """Verifica si es un literal numérico"""
        if not operand.startswith('#'):
            return False
        try:
            float(operand[1:])
            return True
        except ValueError:
            return False
    
    def _evaluate_binary(self, op: str, left: str, right: str) -> Optional[str]:
        """Evalúa una operación binaria con constantes"""
        try:
            l_val = float(left[1:])  # Remove #
            r_val = float(right[1:])
            
            if op == '+':
                result = l_val + r_val
            elif op == '-':
                result = l_val - r_val
            elif op == '*':
                result = l_val * r_val
            elif op == '/':
                if r_val == 0:
                    return None  # División por cero
                result = l_val / r_val
            elif op == '%':
                if r_val == 0:
                    return None
                result = l_val % r_val
            elif op == '==':
                result = 1 if l_val == r_val else 0
            elif op == '!=':
                result = 1 if l_val != r_val else 0
            elif op == '<':
                result = 1 if l_val < r_val else 0
            elif op == '<=':
                result = 1 if l_val <= r_val else 0
            elif op == '>':
                result = 1 if l_val > r_val else 0
            elif op == '>=':
                result = 1 if l_val >= r_val else 0
            else:
                return None
            
            # Convertir a entero si ambos operandos son enteros
            if '.' not in left[1:] and '.' not in right[1:] and op not in ['==', '!=', '<', '<=', '>', '>=']:
                # Para división, mantener como entero solo si es división exacta
                if op == '/' and result != int(result):
                    pass  # Mantener como float
                else:
                    result = int(result)
            
            return f"#{result}"
            
        except (ValueError, ZeroDivisionError):
            return None

class TacOptimizer:
    """
    Orchestador principal de las optimizaciones TAC
    """
    
    def __init__(self):
        self.passes = [
            ConstantFoldingPass(),      # Primero plegamos constantes
            TempEliminationPass(),      # Luego eliminamos temporales redundantes
            ConstantFoldingPass(),      # Segundo pase de constantes (después de eliminar temporales)
            DeadCodeEliminationPass(),  # Eliminamos código muerto
            PeepholeOptimizationPass(), # Optimizaciones peephole
            ConstantFoldingPass(),      # Pase final de constantes
        ]
    
    def optimize(self, program: TacProgram) -> TacProgram:
        """Aplica todas las optimizaciones al programa"""
        for optimization_pass in self.passes:
            program = optimization_pass.optimize_program(program)
        return program