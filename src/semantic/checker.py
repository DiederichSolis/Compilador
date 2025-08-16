# src/semantic/checker.py
from __future__ import annotations
from typing import Optional, List
from dataclasses import dataclass

from antlr4 import ParserRuleContext, Token
from parsing.antlr.CompiscriptVisitor import CompiscriptVisitor
from parsing.antlr.CompiscriptParser import CompiscriptParser

from .types import INT, BOOL, STR, NULL, VOID, ArrayType, ClassType, Type
from .symbols import VariableSymbol, FunctionSymbol, ClassSymbol, ParamSymbol, Symbol
from .symbol_table import SymbolTable
from .diagnostics import Diagnostics

# ---------------------------
# Helpers de ubicación
# ---------------------------
def where(ctx: ParserRuleContext) -> tuple[int, int]:
    t: Optional[Token] = getattr(ctx, "start", None)
    return ((t.line or 0), (t.column or 0)) if t else (0, 0)

# ---------------------------
# Checador principal
# ---------------------------
class CompiscriptSemanticVisitor(CompiscriptVisitor):
    """
    Visitor semántico adaptado a la gramática Compiscript.g4 del usuario.
    Ajusta si cambias reglas en el .g4.
    """

    def __init__(self):
        self.diag = Diagnostics()
        self.symtab = SymbolTable()
        self._in_loop = 0
        self._current_function: Optional[FunctionSymbol] = None

    # ---------- Utilidades ----------
    def error(self, code: str, msg: str, ctx: ParserRuleContext, **extra):
        line, col = where(ctx)
        self.diag.add(phase="semantic", code=code, message=msg, line=line, col=col, **extra)

    def define_var(self, name: str, typ: Type, ctx: ParserRuleContext):
        try:
            self.symtab.current.define(VariableSymbol(name=name, type=typ))
        except KeyError:
            self.error("E001", f"Redeclaración de '{name}'", ctx, name=name)

    def define_func(self, func: FunctionSymbol, ctx: ParserRuleContext):
        try:
            self.symtab.current.define(func)
        except KeyError:
            self.error("E001", f"Redeclaración de función '{func.name}'", ctx, name=func.name)

    def define_class(self, cls: ClassSymbol, ctx: ParserRuleContext):
        try:
            self.symtab.current.define(cls)
        except KeyError:
            self.error("E001", f"Redeclaración de clase '{cls.name}'", ctx, name=cls.name)

    def resolve(self, name: str, ctx: ParserRuleContext) -> Optional[Symbol]:
        sym = self.symtab.current.resolve(name)
        if sym is None:
            self.error("E002", f"Símbolo no definido '{name}'", ctx, name=name)
        return sym

    # ---------- Programa ----------
    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        # Pase 1: firmas de funciones y clases (recorre statements)
        for st in ctx.statement() or []:
            if st.functionDeclaration():
                self._collect_function_signature(st.functionDeclaration())
            if st.classDeclaration():
                self._collect_class_signature(st.classDeclaration())
        # Pase 2: visita ya con símbolos base
        return self.visitChildren(ctx)

    # --- firmas de función ---
    def _collect_function_signature(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        name = ctx.Identifier().getText()
        params: List[ParamSymbol] = []
        if ctx.parameters():
            for p in ctx.parameters().parameter():
                pname = p.Identifier().getText()
                ptype = self._read_type(p.type_()) if p.type_() else None   # << aquí
                params.append(ParamSymbol(name=pname, type=ptype or INT))
        ret = self._read_type(ctx.type_()) if ctx.type_() else VOID          # << y aquí
        self.define_func(FunctionSymbol(name=name, type=ret, params=params), ctx)


    def _collect_class_signature(self, ctx: CompiscriptParser.ClassDeclarationContext):
        name = ctx.Identifier(0).getText()  # el primero es el nombre de la clase
        cls_type = ClassType(name, {})      # puedes poblar members luego
        self.define_class(ClassSymbol(name=name, type=cls_type), ctx)

    # --- variable/const ---
    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name = ctx.Identifier().getText()
        annotated = self._read_type(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None  # << aquí
        init_t = self.visit(ctx.initializer().expression()) if ctx.initializer() else None
        vtype = annotated or (init_t if isinstance(init_t, Type) else INT)
        self.define_var(name, vtype, ctx)
        if init_t is not None and annotated is not None and init_t != annotated:
            self.error("E101", f"Asignación incompatible: {annotated} = {init_t}", ctx)
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        name = ctx.Identifier().getText()
        annotated = self._read_type(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None  # << y aquí
        init_t = self.visit(ctx.expression())
        vtype = annotated or (init_t if isinstance(init_t, Type) else INT)
        self.define_var(name, vtype, ctx)
        if annotated is not None and init_t != annotated:
            self.error("E101", f"Asignación incompatible: const {annotated} = {init_t}", ctx)
        return None

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        # 1) Identifier '=' expression ';'
        # 2) expression '.' Identifier '=' expression ';'

        exprs = ctx.expression()
        if not isinstance(exprs, list):
            exprs = [exprs] if exprs is not None else []

        if len(exprs) == 1:
            # Variante 1: asignación a variable
            name = ctx.Identifier().getText()  # ← sin índice
            sym = self.resolve(name, ctx)
            et = self.visit(exprs[0])
            if sym and et and sym.type != et:
                self.error("E101", f"Asignación incompatible: {sym.type} = {et}", ctx)
            return None

        elif len(exprs) == 2:
            # Variante 2: asignación a propiedad: obj.prop = valor
            obj_t = self.visit(exprs[0])
            prop_name = ctx.Identifier().getText()  # ← sin índice
            val_t = self.visit(exprs[1])

            if isinstance(obj_t, ClassType):
                expected = obj_t.members.get(prop_name)
                if expected is not None and expected != val_t:
                    self.error("E101", f"Asignación incompatible a miembro '{prop_name}': {expected} = {val_t}", ctx)
            else:
                self.error("E301", "Asignación de propiedad sobre tipo no-clase", ctx)
            return None

        self.error("E999", "Forma de asignación no reconocida", ctx)
        return None

    # ---------- Statements ----------
    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        self.symtab.push("BLOCK")
        self.visitChildren(ctx)
        self.symtab.pop()
        return None

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        ct = self.visit(ctx.expression())
        if ct != BOOL:
            self.error("E101", f"La condición del if debe ser Bool, recibió {ct}", ctx)
        self.visit(ctx.block(0))
        if ctx.block(1):
            self.visit(ctx.block(1))
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        ct = self.visit(ctx.expression())
        if ct != BOOL:
            self.error("E101", f"La condición del while debe ser Bool, recibió {ct}", ctx)
        self._in_loop += 1
        self.visit(ctx.block())
        self._in_loop -= 1
        return None

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        self._in_loop += 1
        self.visit(ctx.block())
        self._in_loop -= 1
        ct = self.visit(ctx.expression())
        if ct != BOOL:
            self.error("E101", f"La condición del do-while debe ser Bool, recibió {ct}", ctx)
        return None

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        # for '(' (variableDeclaration | assignment | ';') expression? ';' expression? ')' block;
        self._in_loop += 1
        # init: si no es ';', vendrá en children; ANTLR ya lo visitará via visitChildren
        if ctx.expression(0):
            ct = self.visit(ctx.expression(0))
            if ct != BOOL:
                self.error("E101", f"La condición del for debe ser Bool, recibió {ct}", ctx)
        if ctx.block():
            self.visit(ctx.block())
        self._in_loop -= 1
        return None

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        # foreach '(' Identifier 'in' expression ')' block;
        iter_t = self.visit(ctx.expression())
        # (opcional) validar que iter_t sea ArrayType
        if not isinstance(iter_t, ArrayType):
            self.error("E301", f"foreach requiere Array, recibió {iter_t}", ctx)
        self._in_loop += 1
        self.visit(ctx.block())
        self._in_loop -= 1
        return None

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        if self._in_loop <= 0:
            self.error("E201", "break fuera de un bucle", ctx)
        return None

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if self._in_loop <= 0:
            self.error("E201", "continue fuera de un bucle", ctx)
        return None

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        if self._current_function is None:
            self.error("E103", "return fuera de una función", ctx)
            return None
        expr = ctx.expression()
        rt = None if expr is None else self.visit(expr)
        expected = self._current_function.type
        if expected == VOID and rt is not None:
            self.error("E103", f"La función no retorna valor, pero se retornó {rt}", ctx)
        if expected != VOID and (rt is None or rt != expected):
            self.error("E103", f"Tipo de retorno esperado {expected}, recibido {rt}", ctx)
        return None

    # ---------- Funciones y clases ----------
    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        name = ctx.Identifier().getText()
        sym = self.symtab.current.resolve(name)
        if isinstance(sym, FunctionSymbol):
            prev = self._current_function
            self._current_function = sym
            self.symtab.push("FUNCTION", name)
            # define params en scope
            for p in sym.params:
                try:
                    self.symtab.current.define(p)
                except KeyError:
                    self.error("E001", f"Parámetro duplicado '{p.name}'", ctx)
            # visita cuerpo
            self.visit(ctx.block())
            self.symtab.pop()
            self._current_function = prev
        return None

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        name = ctx.Identifier(0).getText()
        self.symtab.push("CLASS", name)
        self.visitChildren(ctx)
        self.symtab.pop()
        return None

    # ---------- Expresiones y literales ----------
    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext):
        exprs = ctx.expression()
        elems = [self.visit(e) for e in (exprs or [])]
        if not elems:
            return ArrayType(NULL)
        first = elems[0]
        for e in elems[1:]:
            if e != first:
                self.error("E101", "Array con tipos heterogéneos", ctx)
                return ArrayType(first)
        return ArrayType(first)

    def visitIndexExpr(self, ctx: CompiscriptParser.IndexExprContext):
        # suffixOp: '[' expression ']' aplicado a una leftHandSide previa
        idxt = self.visit(ctx.expression())
        if idxt != INT:
            self.error("E401", "Índice de arreglo debe ser Int", ctx)
        # el tipo base viene del nodo previo en la cadena; si el visitor se arma recursivo,
        # ANTLR ya resolverá la composición. Aquí devolvemos un tipo "desconocido seguro"
        # Si el hijo izquierdo devolvió ArrayType, lo propaga; si no, error
        # (esta implementación asume que CompiscriptVisitor ya compone)
        return NULL  # conservador; puedes mejorar con atributos sintetizados

    def visitPropertyAccessExpr(self, ctx: CompiscriptParser.PropertyAccessExprContext):
        # '.' Identifier sobre el objeto previo; ver comentario de IndexExpr
        return NULL

    def visitCallExpr(self, ctx: CompiscriptParser.CallExprContext):
        # '(' arguments? ')' sobre el callee previo; aquí podrías validar aridad si conoces la función
        return NULL

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        if len(ctx.multiplicativeExpr()) == 1:
            return self.visit(ctx.multiplicativeExpr(0))
        # forma binaria izq op der (se repite por cierre +*)
        # tomamos la última operación como tipo resultante
        t = self.visit(ctx.multiplicativeExpr(0))
        for i in range(1, len(ctx.multiplicativeExpr())):
            rt = self.visit(ctx.multiplicativeExpr(i))
            # operador está en ctx.getChild(1), 3, 5, ... pero no necesitamos el símbolo
            if t == INT and rt == INT:
                t = INT
            elif t == STR or rt == STR:
                # concatenación con +
                t = STR
            else:
                self.error("E101", f"Operación aditiva incompatible: {t} y {rt}", ctx)
        return t

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        if len(ctx.unaryExpr()) == 1:
            return self.visit(ctx.unaryExpr(0))
        t = self.visit(ctx.unaryExpr(0))
        for i in range(1, len(ctx.unaryExpr())):
            rt = self.visit(ctx.unaryExpr(i))
            if t == INT and rt == INT:
                t = INT
            else:
                self.error("E101", f"Operación multiplicativa incompatible: {t} y {rt}", ctx)
        return t

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            t = self.visit(ctx.unaryExpr())
            if op == '-' and t != INT:
                self.error("E101", f"Negación requiere Int, recibió {t}", ctx)
                return INT
            if op == '!' and t != BOOL:
                self.error("E101", f"NOT requiere Bool, recibió {t}", ctx)
                return BOOL
            return t
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide():
            return self.visit(ctx.leftHandSide())
        if ctx.expression():
            return self.visit(ctx.expression())  # '(' expression ')'
        return None

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        # literalExpr
        #   : Literal
        #   | arrayLiteral
        #   | 'null'
        #   | 'true'
        #   | 'false'
        #   ;
        if ctx.Literal():
            tok = ctx.Literal().getSymbol()
            text = tok.text or ""
            # Si empieza con comillas => String, si no => Integer (tu lexer define ambas variantes dentro de Literal)
            if text.startswith('"'):
                return STR
            return INT

        if ctx.arrayLiteral():
            return self.visit(ctx.arrayLiteral())

        txt = ctx.getText()
        if txt == "null":
            return NULL
        if txt == "true" or txt == "false":
            return BOOL

        return None


    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        name = ctx.Identifier().getText()
        sym = self.resolve(name, ctx)
        return sym.type if isinstance(sym, Symbol) else None

    def visitThisExpr(self, ctx: CompiscriptParser.ThisExprContext):
        # si modelas 'this', puedes devolver ClassType del scope actual de clase
        return None

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        cname = ctx.Identifier().getText()
        # si tienes ClassSymbol en la tabla, puedes resolver y devolver ClassType
        sym = self.resolve(cname, ctx)
        if isinstance(sym, ClassSymbol):
            return sym.type
        # si no existe, marcará E002 en resolve
        return None

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        # equalityExpr : relationalExpr (('==' | '!=') relationalExpr)* ;
        n = len(ctx.relationalExpr())
        if n == 1:
            return self.visit(ctx.relationalExpr(0))  # <- PROPAGA TIPO
        # Con operador, siempre devuelve Bool (y podrías validar compatibilidad)
        _ = self.visit(ctx.relationalExpr(0))
        _ = self.visit(ctx.relationalExpr(1))
        return BOOL


    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        # relationalExpr : additiveExpr (('<' | '<=' | '>' | '>=') additiveExpr)* ;
        n = len(ctx.additiveExpr())
        if n == 1:
            return self.visit(ctx.additiveExpr(0))  # <- PROPAGA TIPO
        # Con operador relacional, devuelve Bool (valida que sean enteros si quieres)
        _ = self.visit(ctx.additiveExpr(0))
        _ = self.visit(ctx.additiveExpr(1))
        return BOOL


    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        # logicalAndExpr : equalityExpr ('&&' equalityExpr)* ;
        n = len(ctx.equalityExpr())
        if n == 1:
            return self.visit(ctx.equalityExpr(0))  # <- PROPAGA TIPO (p.ej. true)
        # Con '&&' debe ser Bool && Bool, y devuelve Bool
        for i in range(n):
            t = self.visit(ctx.equalityExpr(i))
            if t != BOOL:
                self.error("E101", f"AND requiere Bool, recibió {t}", ctx)
        return BOOL


    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        # logicalOrExpr : logicalAndExpr ('||' logicalAndExpr)* ;
        n = len(ctx.logicalAndExpr())
        if n == 1:
            return self.visit(ctx.logicalAndExpr(0))  # <- PROPAGA TIPO
        # Con '||' debe ser Bool || Bool, y devuelve Bool
        for i in range(n):
            t = self.visit(ctx.logicalAndExpr(i))
            if t != BOOL:
                self.error("E101", f"OR requiere Bool, recibió {t}", ctx)
        return BOOL


    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext):
        # conditionalExpr: logicalOrExpr ('?' expression ':' expression)? ;
        if ctx.getChildCount() == 1:
            return self.visit(ctx.logicalOrExpr())  # <- PROPAGA TIPO
        ct = self.visit(ctx.logicalOrExpr())
        if ct != BOOL:
            self.error("E101", f"Condición del operador ternario debe ser Bool, recibió {ct}", ctx)
        tt = self.visit(ctx.expression(0))
        ft = self.visit(ctx.expression(1))
        return tt


    # --- lectura de tipos ---
    def _read_type(self, tctx: Optional[CompiscriptParser.TypeContext]) -> Optional[Type]:
        if tctx is None:
            return None
        base = self._read_base_type(tctx.baseType())
        txt = tctx.getText()
        brackets = txt.count("[]")            # contar '[]' es lo más fiable
        typ: Type = base or NULL
        for _ in range(brackets):
            typ = ArrayType(typ)
        return typ


    def _read_base_type(self, bctx: Optional[CompiscriptParser.BaseTypeContext]) -> Optional[Type]:
        if bctx is None:
            return None
        txt = bctx.getText()
        if txt == "integer":
            return INT
        if txt == "boolean":
            return BOOL
        if txt == "string":
            return STR
        if txt == "void":                 # <<--- añade esto
            return VOID

        # Identificador de clase/alias de tipo
        sym = self.resolve(txt, bctx)
        if isinstance(sym, ClassSymbol):
            return sym.type
        # Si aún no existe, tratamos como tipo nominal de clase
        return ClassType(txt, {})


# ---------------------------
# Facade
# ---------------------------
def analyze(tree) -> dict:
    """
    Ejecuta el checker sobre un parse tree y devuelve:
      { "symbols": [...], "errors": [...] }
    """
    checker = CompiscriptSemanticVisitor()
    checker.visit(tree)
    return {"symbols": checker.symtab.dump(), "errors": checker.diag.to_list()}
