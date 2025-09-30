from antlr4 import InputStream, CommonTokenStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from ir.backend.tac_generator import TacGen

def _tac(code: str) -> str:
    lx = CompiscriptLexer(InputStream(code))
    ts = CommonTokenStream(lx)
    px = CompiscriptParser(ts)
    tree = px.program()
    gen = TacGen()
    gen.visit(tree)
    return gen.prog.dump()

def test_array_literal_emits_newarr_and_stores():
    code = """
    function main(){
      let arr: integer[] = [1,2,3];
      print(arr[1]);
    }"""
    t = _tac(code)
    assert "newarr integer, #3" in t
    assert "astore" in t
    assert "aload" in t

def test_foreach_on_literal_uses_known_length_or_len():
    code = """
    function main(){
      let acc: integer = 0;
      foreach (x in [10,20]) {
        acc = acc + x;
      }
      print(acc);
    }"""
    t = _tac(code)
    # aceptamos cualquiera de los dos: tamaño constante o len()
    assert "aload" in t
    assert ("< #2" in t) or ("call len, 1" in t)

def test_foreach_on_var_calls_len():
    code = """
    function main(){
      let acc: integer = 0;
      let arr: integer[] = [1,2,3];
      foreach (x in arr) {
        acc = acc + x;
      }
      print(acc);
    }"""
    t = _tac(code)
    assert "call len, 1" in t
    assert "aload" in t