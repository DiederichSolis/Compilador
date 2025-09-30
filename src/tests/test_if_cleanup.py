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

def test_if_both_branches_return_has_no_end_goto():
    code = """
    function max(a: integer, b: integer): integer {
      if (a > b) {
        return a;
      } else {
        return b;
      }
    }"""
    t = _tac(code)
    # No debe existir un 'goto Lend...' en la rama then
    assert "goto Lend" not in t
    # Se permite que no exista 'Lend' label en absoluto
    # Debe existir un único label de retorno (implícito de la función)
    assert "Lret" in t