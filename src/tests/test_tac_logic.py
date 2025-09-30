from antlr4 import CommonTokenStream, InputStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from ir.backend.tac_generator import TacGen

def _gen_tac(code: str) -> str:
    stream = InputStream(code)
    lexer = CompiscriptLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    assert parser.getNumberOfSyntaxErrors() == 0
    gen = TacGen()
    gen.visit(tree)
    return gen.prog.dump()

def test_logical_or_short_circuit():
    code = """
    function main() {
      let a: boolean = true;
      let b: boolean = false;
      if (a || b) { print(1); } else { print(0); }
    }
    """
    tac = _gen_tac(code)
    # Debe contener un salto condicional directo tras evaluar 'a'
    assert "if " in tac or "ifFalse " in tac
    assert "Lor_end" in tac  # etiqueta OR
    # Debe haber dos prints en el TAC de if/else
    assert tac.count("print") >= 2

def test_logical_and_short_circuit():
    code = """
    function main() {
      let a: boolean = false;
      let b: boolean = true;
      if (a && b) { print(1); } else { print(0); }
    }
    """
    tac = _gen_tac(code)
    # Debe saltar si 'a' es false
    assert "ifFalse" in tac
    assert "Land_end" in tac
    assert tac.count("print") >= 2