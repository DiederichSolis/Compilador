from antlr4 import CommonTokenStream, InputStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from ir.backend.tac_generator import TacGen

def _tac(code: str) -> str:
    stream = InputStream(code)
    lexer = CompiscriptLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    assert parser.getNumberOfSyntaxErrors() == 0
    gen = TacGen(); gen.visit(tree)
    return gen.prog.dump()

def test_no_goto_followed_by_same_label():
    code = """
    function main(){
      let i:integer = 0;
      while (i < 3) {
        if (i == 1) { i = i + 1; continue; }
        if (i == 2) { break; }
        i = i + 1;
      }
    }"""
    tac = _tac(code)
    # No debe existir ninguna ocurrencia goto Lx justo antes de "Lx:"
    lines = [ln.strip() for ln in tac.splitlines()]
    for a, b in zip(lines, lines[1:]):
        if a.startswith("goto ") and b.endswith(":"):
            label = a.split()[1]
            assert b[:-1] != label, f"Redundant 'goto {label}' before '{label}:' found"