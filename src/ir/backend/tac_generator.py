# src/backend/tac_generator.py
from __future__ import annotations
from typing import Optional, List, Tuple, Dict
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
    if text.startswith('"'): return f'#"{text[1:-1]}"'
    return f"#{text}"

def local(name: str) -> str:  return f"%{name}"
def global_(name: str) -> str: return f"@{name}"

@dataclass
class TacGen(CompiscriptVisitor):
    prog: TacProgram = field(default_factory=TacProgram)
    cur: Optional[Emitter] = None
    _func_stack: List[dict] = field(default_factory=list)
    _loop: List[Tuple[str, str]] = field(default_factory=list)
    _arr_len: Dict[str, int] = field(default_factory=dict)
    _break: List[str] = field(default_factory=list) 
    _switch: List[str] = field(default_factory=list)
    # ===== funciones =====
    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        """
        PASES:
        1) Declarar firmas de funciones (para poder llamarlas desde top-level).
        2) Crear función implícita 'main' y generar TODO el código ejecutable de nivel superior ahí
            (let/var/const, asignaciones, prints, if/while/for/foreach/switch/try, etc.).
            Se SALTAN classDeclaration y functionDeclaration.
        3) Generar cuerpos de funciones declaradas (visitFunctionDeclaration).
        """
        # ----- Pase 1: sólo firmas de funciones -----
        for st in ctx.statement() or []:
            if st.functionDeclaration():
                self._declare_function(st.functionDeclaration())

        # ----- Pase 2: generar "main" implícito para el código de nivel superior -----
        main_fn = TacFunction(name="main", params=[], ret="void")
        self.prog.add(main_fn)

        prev = self.cur
        self.cur = Emitter(main_fn)
        self.cur.label("f_main")

        # Visitar SOLO los statements ejecutables a nivel superior
        for st in ctx.statement() or []:
            if st.functionDeclaration() or st.classDeclaration():
                continue  # no son ejecutables directamente
            self.visit(st)

        # Retorno del main
        self.cur.ret()

        # Restaurar emisor anterior
        self.cur = prev

        # ----- Pase 3: generar cuerpos de funciones -----
        for st in ctx.statement() or []:
            if st.functionDeclaration():
                self.visit(st.functionDeclaration())

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
        name = ctx.Identifier().getText()
        tfn = next(f for f in self.prog.functions if f.name == name)
        prev = self.cur
        self.cur = Emitter(tfn)

        ret_label = self.cur.L("Lret")
        ret_temp  = self.cur.t()
        ret_type  = (tfn.ret or "Void").lower()
        self._func_stack.append({
            "name": name, "ret_label": ret_label, "ret_temp": ret_temp,
            "has_return": False, "ret_type": ret_type,
        })

        self.cur.label(f"f_{name}")

        # cuerpo
        self.visit(ctx.block())

        # 🔧 limpia gotos triviales antes de armar el epílogo
        tfn.code = self._peephole(tfn.code)

        # epílogo único
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
            else:
                self.cur.move("#0", local(name))
            return None

        # Si por alguna razón se visita fuera de función (no debería, tenemos main implícito),
        # lo ignoramos silenciosamente o podrías moverlo a un mapa de @globales en self.prog.
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
        self.cur.setf(obj, field, val)
        return None
    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        cond = self.visit(ctx.expression())

        has_else = ctx.block(1) is not None

        if not has_else:
            # if (cond) { then }      // sin else
            L_after = self.cur.L("Lend")  # usamos un único label de salida
            self.cur.if_false(cond, L_after)
            self.visit(ctx.block(0))
            if not self.cur.last_is_terminal():
                self.cur.goto(L_after)
            self.cur.label(L_after)
            return None

        # if (cond) { then } else { els }
        L_else = self.cur.L("Lelse")
        # L_end lo crearemos sólo si lo necesitamos
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

        # Etiqueta de salida sólo si alguna rama no es terminal
        if not then_term or not else_term:
            if L_end is None:
                L_end = self.cur.L("Lend")
            self.cur.label(L_end)

        return None

    # ===== expresiones =====
    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr(): return self.visit(ctx.literalExpr())
        if ctx.leftHandSide(): return self.visit(ctx.leftHandSide())
        if ctx.expression(): return self.visit(ctx.expression())
        return "#0"

   # LHS chaining: primaryAtom (suffixOp)*
    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        base = self.visit(ctx.primaryAtom())

        for sop in ctx.suffixOp() or []:
            k = sop.start.text

            if k == '(':
                # llamada: f(...), obj.m(...), (expr)(...)
                args = []
                if getattr(sop, "arguments", None) and sop.arguments():
                    args = [self.visit(e) for e in (sop.arguments().expression() or [])]
                for a in args:
                    self.cur.param(a)

                # ✅ normalizar callee: si viene como "%inc", usar "inc"
                callee = base[1:] if isinstance(base, str) and base.startswith('%') else base

                tmp = self.cur.t()
                self.cur.call(callee, len(args), tmp)
                base = tmp

            elif k == '[':
                # indexación: arr[idx]
                idx = self.visit(sop.expression())
                tmp = self.cur.t()
                self.cur.aload(base, idx, tmp)
                base = tmp

            elif k == '.':
                # acceso a propiedad: obj.prop
                fld = sop.Identifier().getText()
                tmp = self.cur.t()
                self.cur.getf(base, fld, tmp)
                base = tmp

        return base


    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        # para TAC simple tratamos el identificador como operando directo local
        return local(ctx.Identifier().getText())

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        cls = ctx.Identifier().getText()
        tmp = self.cur.t()
        self.cur.new(cls, tmp)
        # si hay argumentos, puedes llamar a init como método: tmp.init(...)
        return tmp

    # Aritmética / lógica / relacional (binop en cascada)
    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        t = self.visit(ctx.multiplicativeExpr(0))
        for i in range(1, len(ctx.multiplicativeExpr())):
            rhs = self.visit(ctx.multiplicativeExpr(i))
            op = ctx.getChild(2*i-1).getText()   # '+' | '-'
            dst = self.cur.t()
            self.cur.bin(op, t, rhs, dst)
            t = dst
        return t

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        t = self.visit(ctx.unaryExpr(0))
        for i in range(1, len(ctx.unaryExpr())):
            rhs = self.visit(ctx.unaryExpr(i))
            op = ctx.getChild(2*i-1).getText()   # '*' | '/' | '%'
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
            # return fuera de función: ignora o reporta; aquí solo emite 'ret' para no romper
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
        # a || b
        # t = a; if t goto L_end; t = b; L_end:
        t = self.visit(ctx.logicalAndExpr(0))
        if len(ctx.logicalAndExpr()) == 1:
            return t
        dst = self.cur.t()
        self.cur.move(t, dst)
        L_end = self.cur.L("Lor_end")
        # si ya es true, saltamos y conservamos dst==true
        self.cur.if_goto(dst, L_end)
        # evaluar el resto en cascada: OR es asociativo izquierda
        for i in range(1, len(ctx.logicalAndExpr())):
            rhs = self.visit(ctx.logicalAndExpr(i))
            self.cur.move(rhs, dst)
            # si ya dio true en cualquier punto, podemos cerrar
            self.cur.if_goto(dst, L_end)
        self.cur.label(L_end)
        return dst

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        # a && b
        # t = a; ifFalse t goto L_end; t = b; L_end:
        t = self.visit(ctx.equalityExpr(0))
        if len(ctx.equalityExpr()) == 1:
            return t
        dst = self.cur.t()
        self.cur.move(t, dst)
        L_end = self.cur.L("Land_end")
        # si ya es false, saltamos y conservamos dst==false
        self.cur.if_false(dst, L_end)
        for i in range(1, len(ctx.equalityExpr())):
            rhs = self.visit(ctx.equalityExpr(i))
            self.cur.move(rhs, dst)
            # si ahora es false, cerramos
            self.cur.if_false(dst, L_end)
        self.cur.label(L_end)
        return dst
    
    def visitConditionalExpr(self, ctx: CompiscriptParser.ConditionalExprContext):
        # cond ? x : y
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
        # repetir mientras cond sea true
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
        Si no hay '?', solo devuelve logicalOrExpr.
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
        # Caso variable simple: Identifier sin sufijos -> %id = <valor>
        # Otros casos (arr[i], obj.f) los cubre PropertyAssignExpr (y opcionalmente arr store).
        val = self.visit(ctx.assignmentExpr())
        lhs = ctx.leftHandSide()
        # ¿es un identificador simple?
        if lhs.primaryAtom() and lhs.primaryAtom().Identifier() and len(lhs.suffixOp() or []) == 0:
            name = lhs.primaryAtom().Identifier().getText()
            self.cur.move(val, f"%{name}")
            return f"%{name}"
        # Si no es simple, lo ignora aquí (lo manejará PropertyAssignExpr o queda como trabajo futuro)
        return val

    def visitPropertyAssignExpr(self, ctx: CompiscriptParser.PropertyAssignExprContext):
        # assignmentExpr: lhs=leftHandSide '.' Identifier '=' assignmentExpr # PropertyAssignExpr
        obj = self.visit(ctx.leftHandSide())
        field = ctx.Identifier().getText()
        val = self.visit(ctx.assignmentExpr())
        self.cur.setf(obj, field, val)
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
        if ctx.getText() == "true":  return "#1"
        if ctx.getText() == "false": return "#0"
        if ctx.getText() == "null":  return "#null"
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

        # En un runtime real, aquí habría instrucción para registrar handler:
        # self.cur.try_(L_catch)   # no implementada; documental

        # Emitir try
        self.visit(ctx.block(0))
        self.cur.goto(L_end)

        # Punto de entrada del catch (por ahora solo estructural)
        self.cur.label(L_catch)
        # El nombre del catch (Identifier) se ignora en TAC mínimo
        self.visit(ctx.block(1))

        self.cur.label(L_end)
        return None














