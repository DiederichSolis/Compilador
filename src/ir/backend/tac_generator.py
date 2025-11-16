# src/backend/tac_generator.py
from __future__ import annotations
from typing import Optional, List, Tuple, Dict, Set
from dataclasses import dataclass, field

from parsing.antlr.CompiscriptVisitor import CompiscriptVisitor
from parsing.antlr.CompiscriptParser import CompiscriptParser

from ir.tac.program import TacProgram, TacFunction
from ir.tac.emitter import Emitter

# Convenciones simples de operandos:
#  - locales/vars:  %<name>
#  - globales:      @<name>
#  - temporales:    tN (creados por emitter)
#  - literales:     #<lexema>  (#"texto" para strings)

def lit(text: str) -> str:
    if text.startswith('"'):
        return f'#"{text[1:-1]}"'
    return f"#{text}"

def local(name: str) -> str:
    return f"%{name}"

def global_(name: str) -> str:
    return f"@{name}"


@dataclass
class TacGen(CompiscriptVisitor):
    prog: TacProgram = field(default_factory=TacProgram)
    cur: Optional[Emitter] = None

    _func_stack: List[dict] = field(default_factory=list)
    _loop: List[Tuple[str, str]] = field(default_factory=list)
    _arr_len: Dict[str, int] = field(default_factory=dict)
    _break: List[str] = field(default_factory=list)
    _switch: List[str] = field(default_factory=list)

    _current_class: Optional[str] = None

    # Info de clases / tipos
    _class_offsets: Dict[str, Dict[str, int]] = field(default_factory=dict)   # (por ahora no usado)
    _class_parent: Dict[str, Optional[str]] = field(default_factory=dict)     # Estudiante -> Persona
    _class_methods: Dict[str, Set[str]] = field(default_factory=dict)         # Persona -> {"saludar", ...}

    # Tipos por variable / temporales
    _scopes: List[Dict[str, str]] = field(default_factory=list)               # pila de scopes de tipos
    _temp_types: Dict[str, str] = field(default_factory=dict)                 # tN -> NombreClase

    # ===== helpers de tipos / scopes =====
    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> None:
        if self._scopes:
            self._scopes.pop()

    def _set_type(self, name: str, ty: str) -> None:
        if not self._scopes:
            self._push_scope()
        self._scopes[-1][name] = ty

    def _get_type(self, name: str) -> Optional[str]:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def _set_temp_type(self, op: str, ty: str) -> None:
        # op es algo como t3
        self._temp_types[op] = ty

    def _infer_class_from_operand(self, op: str) -> Optional[str]:
        # %x -> busca tipo de x
        if isinstance(op, str) and op.startswith("%"):
            return self._get_type(op[1:])
        # temporales tN que vienen de "new Clase"
        if isinstance(op, str) and op in self._temp_types:
            return self._temp_types[op]
        # this dentro de un método
        if op == "%this" and self._current_class:
            return self._current_class
        return None

    def _resolve_method(self, cls: str, mname: str) -> str:
        """
        Dado un tipo de objeto y un nombre de método, sube por la jerarquía
        hasta encontrar la clase que lo define. Devuelve Class__method.
        Si no lo encuentra, devuelve simplemente el nombre del método.
        """
        c = cls
        while c:
            methods = self._class_methods.get(c, set())
            if mname in methods:
                return f"{c}__{mname}"
            c = self._class_parent.get(c)
        return mname

    # ===== funciones =====
    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        # Scope global
        self._push_scope()
        stmts = ctx.statement() or []

        # Pase 1: firmas de funciones y métodos
        for st in stmts:
            if st.functionDeclaration():
                self._declare_function(st.functionDeclaration())
            if st.classDeclaration():
                self.visitClassDeclaration(st.classDeclaration())  # declara métodos y jerarquía

        # 💡 Detectar si el usuario declaró un main explícito
        has_explicit_main = any(
            st.functionDeclaration() and st.functionDeclaration().Identifier().getText() == "main"
            for st in stmts
        )

        # Pase 2: main implícito SOLO si NO hay function main()
        if not has_explicit_main:
            main_fn = TacFunction(name="main", params=[], ret="void")
            self.prog.add(main_fn)
            prev = self.cur
            self.cur = Emitter(main_fn)
            self.cur.label("f_main")

            for st in stmts:
                # en main NO generamos de nuevo funciones/clases; solo statements ejecutables
                if st.functionDeclaration() or st.classDeclaration():
                    continue
                self.visit(st)

            self.cur.ret()
            self.cur = prev

        # Pase 3: cuerpos de funciones libres (incluyendo main si existe)
        for st in stmts:
            if st.functionDeclaration():
                self.visit(st.functionDeclaration())

        # Pase 3b: métodos de clases
        for st in stmts:
            if st.classDeclaration():
                class_ctx = st.classDeclaration()
                class_name = class_ctx.Identifier(0).getText()
                self._current_class = class_name
                for member in class_ctx.classMember():
                    if member.functionDeclaration():
                        self.visit(member.functionDeclaration())
                self._current_class = None

        # No hacemos _pop_scope global
        return None

    def _declare_function(self, fctx: CompiscriptParser.FunctionDeclarationContext):
        name = fctx.Identifier().getText()
        params = []
        if fctx.parameters():
            for p in fctx.parameters().parameter():
                params.append(p.Identifier().getText())
        ret = fctx.type_().getText() if fctx.type_() else "Void"
        fn = TacFunction(name=name, params=params, ret=ret)
        self.prog.add(fn)

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        """
        Normal y también para métodos de clase (ya renombrados en _declare_method).
        """
        name = ctx.Identifier().getText()
        if self._current_class:
            name = f"{self._current_class}__{name}"
        tfn = next(f for f in self.prog.functions if f.name == name)
        prev = self.cur
        self.cur = Emitter(tfn)

        # Nuevo scope de tipos para la función
        self._push_scope()

        # Registrar tipos de parámetros
        if self._current_class:
            # this es de tipo _current_class
            self._set_type("this", self._current_class)

        if ctx.parameters():
            for p in ctx.parameters().parameter():
                pname = p.Identifier().getText()
                if p.type_():
                    ptype = p.type_().getText()
                    self._set_type(pname, ptype)

        ret_label = self.cur.L("Lret")
        ret_temp  = self.cur.t()
        ret_type  = (tfn.ret or "Void").lower()
        self._func_stack.append({
            "name": name, "ret_label": ret_label, "ret_temp": ret_temp,
            "has_return": False, "ret_type": ret_type,
        })

        self.visit(ctx.block())

        # epílogo
        fctx = self._func_stack[-1]
        self.cur.label(fctx["ret_label"])
        if fctx["ret_type"] == "void":
            self.cur.ret()
        else:
            if not fctx["has_return"]:
                self.cur.move("#0", fctx["ret_temp"])
            self.cur.ret(fctx["ret_temp"])

        self._func_stack.pop()
        tfn.finalize_frame()
        self.cur = prev

        # cerrar scope de tipos de la función
        self._pop_scope()
        return None

    def _peephole(self, code):
        out = []
        n = len(code)
        i = 0
        from ir.tac.instructions import Goto, Label
        while i < n:
            cur = code[i]
            # patrón: goto L; label L:  -> elimina el goto
            if isinstance(cur, Goto) and i + 1 < n:
                nxt = code[i + 1]
                if isinstance(nxt, Label) and nxt.name == cur.label:
                    i += 1  # salta el goto y deja la label
                    continue
            out.append(cur)
            i += 1
        return out

    # ===== statements =====
    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        v = self.visit(ctx.expression())
        self.cur.print(v)
        return None

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name = ctx.Identifier().getText()

        # Registrar tipo (si viene anotado)
        if ctx.typeAnnotation():
            ty = ctx.typeAnnotation().type_().getText()
            self._set_type(name, ty)


        # Si estamos dentro de función, alocar como local nombrado
        if self.cur is not None:
            try:
                self.cur.fn.locals_count += 1
                self.cur.fn.alloc_local(name)
            except Exception:
                pass
            if ctx.initializer():
                rhs = self.visit(ctx.initializer().expression())
                self.cur.move(rhs, local(name))
                # Si el tipo no venía anotado, inferirlo de un `new Clase`
                if not ctx.typeAnnotation():
                    inferred = self._temp_types.get(rhs)
                    if inferred:
                        self._set_type(name, inferred)
            else:
                self.cur.move("#0", local(name))
            return None

        # Fuera de función (no debería pasar con main implícito)
        return None

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        exprs = ctx.expression()
        if not isinstance(exprs, list):
            exprs = [exprs] if exprs is not None else []

        if len(exprs) == 1:
            # x = expr ;
            name = ctx.Identifier().getText()
            val = self.visit(exprs[0])
            self.cur.move(val, local(name))
            return None

        # obj.prop = expr;
        obj = self.visit(exprs[0])
        val = self.visit(exprs[1])
        field = ctx.Identifier().getText()

        cls = self._infer_class_from_operand(obj)
        if cls is None:
            offset = 0   # o aquí puedes hacer un assert / raise
        else:
            offset = self._class_offsets[cls][field]

        self.cur.setf(obj, offset, val)
        return None

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        cond = self.visit(ctx.expression())
        has_else = ctx.block(1) is not None

        if not has_else:
            L_after = self.cur.L("Lend")
            self.cur.if_false(cond, L_after)
            self.visit(ctx.block(0))
            if not self.cur.last_is_terminal():
                self.cur.goto(L_after)
            self.cur.label(L_after)
            return None

        # if (cond) { then } else { els }
        L_else = self.cur.L("Lelse")
        L_end = None

        self.cur.if_false(cond, L_else)

        # THEN
        self.visit(ctx.block(0))
        then_term = self.cur.last_is_terminal()
        if not then_term:
            if L_end is None:
                L_end = self.cur.L("Lend")
            self.cur.goto(L_end)

        # ELSE
        self.cur.label(L_else)
        self.visit(ctx.block(1))
        else_term = self.cur.last_is_terminal()

        if not then_term or not else_term:
            if L_end is None:
                L_end = self.cur.L("Lend")
            self.cur.label(L_end)

        return None

    # ===== expresiones =====
    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide():
            return self.visit(ctx.leftHandSide())
        if ctx.expression():
            return self.visit(ctx.expression())
        return "#0"

    # LHS chaining: primaryAtom (suffixOp)*
    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        base = self.visit(ctx.primaryAtom())
        suffixes = list(ctx.suffixOp() or [])
        i = 0

        while i < len(suffixes):
            sop = suffixes[i]
            k = sop.start.text

            # Caso especial: obj.metodo(args...)  -> llamada a método
            if k == '.' and i + 1 < len(suffixes) and suffixes[i + 1].start.text == '(':
                fld = sop.Identifier().getText()
                callop = suffixes[i + 1]

                # argumentos explícitos
                args = []
                if getattr(callop, "arguments", None) and callop.arguments():
                    args = [self.visit(e) for e in (callop.arguments().expression() or [])]

                # this + args
                self.cur.param(base)
                for a in args:
                    self.cur.param(a)

                # resolver nombre de función del método
                cls = self._infer_class_from_operand(base)
                if cls:
                    callee = self._resolve_method(cls, fld)
                else:
                    # fallback muy simple
                    callee = fld

                tmp = self.cur.t()
                self.cur.call(callee, 1 + len(args), tmp)
                base = tmp
                i += 2
                continue

            if k == '(':
                # llamada a función simple: f(...)
                args = []
                if getattr(sop, "arguments", None) and sop.arguments():
                    args = [self.visit(e) for e in (sop.arguments().expression() or [])]
                for a in args:
                    self.cur.param(a)

                callee = base[1:] if isinstance(base, str) and base.startswith('%') else base
                tmp = self.cur.t()
                self.cur.call(callee, len(args), tmp)
                base = tmp
                i += 1
                continue

            if k == '[':
                # indexación: arr[idx]
                idx = self.visit(sop.expression())
                tmp = self.cur.t()
                self.cur.aload(base, idx, tmp)
                base = tmp
                i += 1
                continue

            if k == '.':
                # acceso a propiedad: obj.prop
                fld = sop.Identifier().getText()
                tmp = self.cur.t()

                # sacar la clase de "base" (%this, %var, tN de new Clase, etc.)
                cls = self._infer_class_from_operand(base)
                if cls is None:
                    # fallback súper defensivo (puedes hacer raise si quieres)
                    offset = 0
                else:
                    offset = self._class_offsets[cls][fld]

                # ahora getf recibe el offset en bytes
                self.cur.getf(base, offset, tmp)
                base = tmp
                i += 1
                continue


            # Si llegamos aquí, lo dejamos pasar
            i += 1

        return base

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        return local(ctx.Identifier().getText())

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        """
        Traduce:
            new Clase(arg1, arg2, ...)
        a:
            t0 = new Clase
            param t0
            param arg1
            param arg2
            ...
            call Clase__constructor, N+1
        y devuelve t0.
        """
        cls = ctx.Identifier().getText()
        tmp = self.cur.t()
        self.cur.new(cls, tmp)
        # registrar tipo del temporal
        self._set_temp_type(tmp, cls)

        # ¿hay argumentos de constructor?
        if ctx.arguments():
            args = [self.visit(e) for e in (ctx.arguments().expression() or [])]
            # this primero
            self.cur.param(tmp)
            for a in args:
                self.cur.param(a)
            ctor_name = f"{cls}__constructor"
            self.cur.call(ctor_name, 1 + len(args))

        return tmp

    # Aritmética / lógica / relacional (binop en cascada)
    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        t = self.visit(ctx.multiplicativeExpr(0))
        for i in range(1, len(ctx.multiplicativeExpr())):
            rhs = self.visit(ctx.multiplicativeExpr(i))
            op = ctx.getChild(2 * i - 1).getText()   # '+' | '-'
            dst = self.cur.t()
            self.cur.bin(op, t, rhs, dst)
            t = dst
        return t

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        t = self.visit(ctx.unaryExpr(0))
        for i in range(1, len(ctx.unaryExpr())):
            rhs = self.visit(ctx.unaryExpr(i))
            op = ctx.getChild(2 * i - 1).getText()   # '*' | '/' | '%'
            dst = self.cur.t()
            self.cur.bin(op, t, rhs, dst)
            t = dst
        return t

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()  # '-' | '!'
            a = self.visit(ctx.unaryExpr())
            dst = self.cur.t()
            self.cur.unary(op, a, dst)
            return dst
        return self.visit(ctx.primaryExpr())

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        if len(ctx.relationalExpr()) == 1:
            return self.visit(ctx.relationalExpr(0))
        a = self.visit(ctx.relationalExpr(0))
        b = self.visit(ctx.relationalExpr(1))
        op = ctx.getChild(1).getText()  # '==' | '!='
        dst = self.cur.t()
        self.cur.bin(op, a, b, dst)
        return dst

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        if len(ctx.additiveExpr()) == 1:
            return self.visit(ctx.additiveExpr(0))
        a = self.visit(ctx.additiveExpr(0))
        b = self.visit(ctx.additiveExpr(1))
        op = ctx.getChild(1).getText()  # < <= > >=
        dst = self.cur.t()
        self.cur.bin(op, a, b, dst)
        return dst

    # returnStatement: 'return' expression? ';'
    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        if not self._func_stack:
            self.cur.ret()
            return None
        fctx = self._func_stack[-1]
        if ctx.expression():
            v = self.visit(ctx.expression())
            if fctx["ret_type"] != "void":
                self.cur.move(v, fctx["ret_temp"])
        else:
            if fctx["ret_type"] != "void":
                self.cur.move("#0", fctx["ret_temp"])
        fctx["has_return"] = True
        self.cur.goto(fctx["ret_label"])
        return None

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        t = self.visit(ctx.logicalAndExpr(0))
        if len(ctx.logicalAndExpr()) == 1:
            return t
        dst = self.cur.t()
        self.cur.move(t, dst)
        L_end = self.cur.L("Lor_end")
        self.cur.if_goto(dst, L_end)
        for i in range(1, len(ctx.logicalAndExpr())):
            rhs = self.visit(ctx.logicalAndExpr(i))
            self.cur.move(rhs, dst)
            self.cur.if_goto(dst, L_end)
        self.cur.label(L_end)
        return dst

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        t = self.visit(ctx.equalityExpr(0))
        if len(ctx.equalityExpr()) == 1:
            return t
        dst = self.cur.t()
        self.cur.move(t, dst)
        L_end = self.cur.L("Land_end")
        self.cur.if_false(dst, L_end)
        for i in range(1, len(ctx.equalityExpr())):
            rhs = self.visit(ctx.equalityExpr(i))
            self.cur.move(rhs, dst)
            self.cur.if_false(rhs, L_end)
        self.cur.label(L_end)
        return dst

    def visitConditionalExpr(self, ctx: CompiscriptParser.ConditionalExprContext):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.logicalOrExpr())
        cond = self.visit(ctx.logicalOrExpr())
        L_false = self.cur.L("Ltern_false")
        L_end   = self.cur.L("Ltern_end")
        dst     = self.cur.t()
        self.cur.if_false(cond, L_false)
        t_then = self.visit(ctx.expression(0))
        self.cur.move(t_then, dst)
        self.cur.goto(L_end)
        self.cur.label(L_false)
        t_else = self.visit(ctx.expression(1))
        self.cur.move(t_else, dst)
        self.cur.label(L_end)
        return dst

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if not self._loop:
            return None
        L_cond, _ = self._loop[-1]
        self.cur.goto(L_cond)
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        L_cond = self.cur.L("Lcond")
        L_end  = self.cur.L("Lend")
        self.cur.label(L_cond)
        cond = self.visit(ctx.expression())
        self.cur.if_false(cond, L_end)
        self._loop.append((L_cond, L_end))
        self.visit(ctx.block())
        self._loop.pop()
        self.cur.goto(L_cond)
        self.cur.label(L_end)
        return None

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        L_body = self.cur.L("Lbody")
        L_end  = self.cur.L("Lend")
        self.cur.label(L_body)
        self._loop.append((L_body, L_end))
        self.visit(ctx.block())
        self._loop.pop()
        cond = self.visit(ctx.expression())
        self.cur.if_goto(cond, L_body)
        self.cur.label(L_end)
        return None

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        # for '(' (variableDeclaration | assignment | ';') expression? ';' expression? ')' block
        # init
        init = ctx.getChild(2)  # puede ser decl, assign o ';'
        if init.getText() != ';':
            self.visit(init)

        L_cond = self.cur.L("Lcond")
        L_end  = self.cur.L("Lend")
        self.cur.label(L_cond)

        # cond
        cond_expr = ctx.expression(0) if ctx.expression(0) else None
        if cond_expr is not None:
            t = self.visit(cond_expr)
            self.cur.if_false(t, L_end)

        # body
        self._loop.append((L_cond, L_end))
        self.visit(ctx.block())
        self._loop.pop()

        # update (si existe, es expression(1))
        upd_expr = None
        if ctx.expression() and len(ctx.expression()) >= 2:
            upd_expr = ctx.expression(1)
        if upd_expr is not None:
            self.visit(upd_expr)

        self.cur.goto(L_cond)
        self.cur.label(L_end)
        return None

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext):
        """
        Regla etiquetada en la gramática:
        conditionalExpr
            : logicalOrExpr ('?' expression ':' expression)? # TernaryExpr
            ;
        """
        # ¿No hay operador ternario? -> devolver la parte lógica
        qmark = None
        for i in range(ctx.getChildCount()):
            if ctx.getChild(i).getText() == '?':
                qmark = i
                break
        if qmark is None:
            return self.visit(ctx.logicalOrExpr())

        # Sí hay ternario
        cond   = self.visit(ctx.logicalOrExpr())
        L_false = self.cur.L("Ltern_false")
        L_end   = self.cur.L("Ltern_end")
        dst     = self.cur.t()

        self.cur.if_false(cond, L_false)
        t_then = self.visit(ctx.expression(0))
        self.cur.move(t_then, dst)
        self.cur.goto(L_end)
        self.cur.label(L_false)
        t_else = self.visit(ctx.expression(1))
        self.cur.move(t_else, dst)
        self.cur.label(L_end)
        return dst

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext):
        # assignmentExpr: lhs=leftHandSide '=' assignmentExpr  # AssignExpr
        val = self.visit(ctx.assignmentExpr())
        lhs = ctx.leftHandSide()
        # Caso variable simple: Identifier sin sufijos -> %id = <valor>
        if lhs.primaryAtom() and lhs.primaryAtom().Identifier() and len(lhs.suffixOp() or []) == 0:
            name = lhs.primaryAtom().Identifier().getText()
            self.cur.move(val, f"%{name}")
            return f"%{name}"
        # Si no es simple, lo dejamos; PropertyAssignExpr se encarga de arr/obj
        return val

    def visitPropertyAssignExpr(self, ctx: CompiscriptParser.PropertyAssignExprContext):
        obj = self.visit(ctx.leftHandSide())
        field = ctx.Identifier().getText()
        val = self.visit(ctx.assignmentExpr())

        cls = self._infer_class_from_operand(obj)
        if cls is None:
            offset = 0
        else:
            offset = self._class_offsets[cls][field]

        self.cur.setf(obj, offset, val)
        return obj


    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext):
        """
        Genera:
        tA = newarr <elem_type>, #N
        astore tA, #i, <vi>  ; por cada literal
        Devuelve el operando del arreglo (tA) y registra su longitud en _arr_len.
        """
        exprs = ctx.expression() or []
        n = len(exprs)

        # Tipo nominal para el newarr; si manejas tipos reales, ajusta aquí.
        elem_ty_name = "integer"

        size_op = f"#{n}"
        arr = self.cur.t()
        self.cur.newarr(elem_ty_name, size_op, arr)

        for idx, ectx in enumerate(exprs):
            val = self.visit(ectx)
            self.cur.astore(arr, f"#{idx}", val)

        # recuerda el tamaño conocido para optimizar foreach
        self._arr_len[arr] = n
        return arr

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        # ⬇️ ajustado: primero arreglos
        if ctx.arrayLiteral():
            return self.visitArrayLiteral(ctx.arrayLiteral())
        if ctx.Literal():
            txt = ctx.Literal().getText()
            return lit(txt)
        if ctx.getText() == "true":
            return "#1"
        if ctx.getText() == "false":
            return "#0"
        if ctx.getText() == "null":
            return "#null"
        return "#0"

    def visitForeachStatement(self, ctx):
        name = ctx.Identifier().getText()  # x
        self.cur.fn.alloc_local(name)
        try:
            self.cur.fn.locals_count += 1
        except Exception:
            pass

        arr = self.visit(ctx.expression())

        # len(arr)
        self.cur.param(arr)
        n = self.cur.t()
        self.cur.call("len", 1, n)

        # i = 0
        i = self.cur.t()
        self.cur.move("#0", i)

        Lcond = self.cur.L("Lcond")
        Lend  = self.cur.L("Lend")
        self.cur.label(Lcond)
        tcond = self.cur.t()
        self.cur.bin("<", i, n, tcond)
        self.cur.if_false(tcond, Lend)

        # x = aload arr, i
        xi = self.cur.t()
        self.cur.aload(arr, i, xi)
        self.cur.move(xi, f"%{name}")   # <-- usa el local %x

        # cuerpo
        self.visit(ctx.block())

        # i = i + 1; goto Lcond
        iplus = self.cur.t()
        self.cur.bin("+", i, "#1", iplus)
        self.cur.move(iplus, i)
        self.cur.goto(Lcond)
        self.cur.label(Lend)
        return None

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        if self._break:  # dentro de switch
            self.cur.goto(self._break[-1])
            return None
        if self._loop:   # dentro de loop
            L_cond, L_end = self._loop[-1]
            self.cur.goto(L_end)
            return None
        return None

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        # switch (expr) { case e1: S* ; case e2: S* ; ... default: S* ; }
        scrut = self.visit(ctx.expression())
        cases = ctx.switchCase() or []
        has_default = ctx.defaultCase() is not None

        # Prepara labels
        L_cases = [self.cur.L("Lcase") for _ in cases]
        L_default = self.cur.L("Ldefault") if has_default else None
        L_end = self.cur.L("Lswitch_end")

        # Comparaciones y dispatch
        for i, c in enumerate(cases):
            ce = self.visit(c.expression())
            tcmp = self.cur.t()
            self.cur.bin("==", scrut, ce, tcmp)
            self.cur.if_goto(tcmp, L_cases[i])
        if has_default:
            self.cur.goto(L_default)
        else:
            self.cur.goto(L_end)

        # Empuja contexto de break
        self._switch.append(L_end)

        # Emite cada case (con caída implícita si no hay break)
        for i, c in enumerate(cases):
            self.cur.label(L_cases[i])
            for st in (c.statement() or []):
                self.visit(st)

        # Default (si existe)
        if has_default:
            self.cur.label(L_default)
            for st in (ctx.defaultCase().statement() or []):
                self.visit(st)

        # Fin del switch
        self._switch.pop()
        self.cur.label(L_end)
        return None

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        # try { Btry } catch (err) { Bcatch }
        L_end = self.cur.L("Ltry_end")
        L_catch = self.cur.L("Lcatch")

        # Emitir try
        self.visit(ctx.block(0))
        self.cur.goto(L_end)

        # Punto de entrada del catch (por ahora solo estructural)
        self.cur.label(L_catch)
        self.visit(ctx.block(1))

        self.cur.label(L_end)
        return None

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        class_name = ctx.Identifier(0).getText()
        base_name = ctx.Identifier(1).getText() if len(ctx.Identifier()) > 1 else None
        self._class_parent[class_name] = base_name

        fields_local = []
        methods = []

        # miembros de la clase
        for member in ctx.classMember():
            if member.variableDeclaration():
                fname = member.variableDeclaration().Identifier().getText()
                fields_local.append(fname)
            elif member.functionDeclaration():
                m = member.functionDeclaration()
                mname = m.Identifier().getText()
                methods.append(m)
                self._class_methods.setdefault(class_name, set()).add(mname)

        # 🔹 heredar offsets del padre (si existe)
        base_offsets = {}
        if base_name is not None:
            base_offsets = dict(self._class_offsets.get(base_name, {}))

        offsets = dict(base_offsets)
        start_index = len(base_offsets)

        # 🔹 añadir campos propios de la clase al final
        for i, f in enumerate(fields_local):
            offsets[f] = (start_index + i) * 4  # 4 bytes por campo

        self._class_offsets[class_name] = offsets

        # generar firmas de métodos
        for m in methods:
            self._declare_method(class_name, m)

        return None


    def _declare_method(self, class_name, fctx):
        """
        Declara una función estilo Class__method(this, params...)
        """
        name = fctx.Identifier().getText()
        params = ["this"]  # siempre incluye this
        if fctx.parameters():
            for p in fctx.parameters().parameter():
                params.append(p.Identifier().getText())
        ret = fctx.type_().getText() if fctx.type_() else "Void"
        fn_name = f"{class_name}__{name}"
        fn = TacFunction(name=fn_name, params=params, ret=ret)
        self.prog.add(fn)
        return fn

    def _infer_class_of_this(self):
        if not self._func_stack:
            return None
        fname = self._func_stack[-1]["name"]
        if "__" in fname:
            return fname.split("__")[0]
        return None

    def visitThisExpr(self, ctx: CompiscriptParser.ThisExprContext):
        # Representamos `this` como un operando local especial
        return "%this"