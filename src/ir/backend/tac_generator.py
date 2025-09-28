# src/backend/tac_generator.py
from __future__ import annotations
from typing import Optional, List
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

    # ===== funciones =====
    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for st in ctx.statement() or []:
            if st.functionDeclaration():
                self._declare_function(st.functionDeclaration())
        # generar cuerpo
        return self.visitChildren(ctx)

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
            # buscar la TacFunction creada
            tfn = next(f for f in self.prog.functions if f.name == name)
            prev = self.cur
            self.cur = Emitter(tfn)

            # contexto de función (epílogo único)
            ret_label = self.cur.L("Lret")
            ret_temp  = self.cur.t()         # contenedor del valor de retorno
            ret_type  = (tfn.ret or "Void").lower()
            self._func_stack.append({
                "name": name,
                "ret_label": ret_label,
                "ret_temp": ret_temp,
                "has_return": False,
                "ret_type": ret_type,
            })

            # prólogo lógico (puedes ajustar frame size luego)
            self.cur.label(f"f_{name}")

            # cuerpo
            self.visit(ctx.block())

            # epílogo único
            fctx = self._func_stack[-1]
            self.cur.label(fctx["ret_label"])
            if fctx["ret_type"] == "void":
                self.cur.ret()
            else:
                if not fctx["has_return"]:
                    # política: si faltó return en función no-void, retorna #0
                    self.cur.move("#0", fctx["ret_temp"])
                self.cur.ret(fctx["ret_temp"])

            self._func_stack.pop()
            self.cur = prev
            return None


    # ===== statements =====
    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        v = self.visit(ctx.expression())
        self.cur.print(v)
        return None

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name = ctx.Identifier().getText()
        # contar como local nombrada si estamos en una función
        if self.cur is not None:
            try:
                self.cur.fn.locals_count += 1
            except Exception:
                pass
        if ctx.initializer():
            rhs = self.visit(ctx.initializer().expression())
            self.cur.move(rhs, local(name))
        else:
            # sin init: inicializa con #0
            self.cur.move("#0", local(name))
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
        L_else = self.cur.L("Lelse")
        L_end  = self.cur.L("Lend")
        self.cur.if_false(cond, L_else)
        self.visit(ctx.block(0))
        self.cur.goto(L_end)
        self.cur.label(L_else)
        if ctx.block(1):
            self.visit(ctx.block(1))
        self.cur.label(L_end)
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        L_cond = self.cur.L("Lcond")
        L_end  = self.cur.L("Lend")
        self.cur.label(L_cond)
        cond = self.visit(ctx.expression())
        self.cur.if_false(cond, L_end)
        self.visit(ctx.block())
        self.cur.goto(L_cond)
        self.cur.label(L_end)
        return None

    # ===== expresiones =====
    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr(): return self.visit(ctx.literalExpr())
        if ctx.leftHandSide(): return self.visit(ctx.leftHandSide())
        if ctx.expression(): return self.visit(ctx.expression())
        return "#0"

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        if ctx.Literal():
            txt = ctx.Literal().getText()
            return lit(txt)
        if ctx.getText() == "true":  return "#1"
        if ctx.getText() == "false": return "#0"
        if ctx.getText() == "null":  return "#null"
        return "#0"

    # LHS chaining: primaryAtom (suffixOp)*
    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        base = self.visit(ctx.primaryAtom())
        for sop in ctx.suffixOp() or []:
            k = sop.start.text
            if k == '(':
                # call: arguments?
                args = []
                if sop.arguments():
                    args = [self.visit(e) for e in (sop.arguments().expression() or [])]
                for a in args: self.cur.param(a)
                tmp = self.cur.t()
                self.cur.call(base, len(args), tmp)
                base = tmp
            elif k == '[':
                idx = self.visit(sop.expression())
                tmp = self.cur.t()
                self.cur.aload(base, idx, tmp)
                base = tmp
            elif k == '.':
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
