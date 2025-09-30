import pytest
from antlr4 import InputStream, CommonTokenStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from semantic.checker import analyze
from ir.backend.tac_generator import TacGen

def _tac(code: str) -> str:
    inp = InputStream(code)
    lex = CompiscriptLexer(inp)
    tok = CommonTokenStream(lex)
    par = CompiscriptParser(tok)
    tree = par.program()
    sem = analyze(tree)
    assert len(sem["errors"]) == 0
    gen = TacGen()
    gen.visit(tree)
    return gen.prog.dump()

def test_switch_basic():
    code = """
    function main(){
      let x: integer = 2;
      switch (x) {
        case 1: print(1);
        case 2: print(2); break;
        case 3: print(3);
        default: print(0);
      }
    }"""
    t = _tac(code)
    assert "Lswitch_end" in t
    # Debe haber saltos a labels de case
    assert "== #2" in t or "== %x, #2" in t

def test_switch_break_and_fallthrough():
    code = """
    function main(){
      let x: integer = 1;
      switch(x){
        case 1: print(1);       // sin break -> cae a case 2
        case 2: print(2); break;
        default: print(0);
      }
    }"""
    t = _tac(code)
    # Debe existir el end del switch
    assert "Lswitch_end" in t

def test_try_catch_shape():
    code = """
    function main(){
      try { print(1); } catch (e) { print(0); }
    }"""
    t = _tac(code)
    # Solo validamos estructura de labels
    assert "Lcatch" in t and "Ltry_end" in t