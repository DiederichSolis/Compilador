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

def test_ternary():
    code = """
    function main(){
      let a:boolean = true;
      let x:integer = a ? 1 : 0;
      print(x);
    }"""
    tac = _tac(code)
    assert "Ltern_false" in tac and "Ltern_end" in tac
    assert "print %x" in tac or "print" in tac  # depende de tu move final

def test_break_continue_in_while():
    code = """
    function main(){
      let i:integer = 0;
      while (i < 5) {
        if (i == 3) { break; }
        if (i == 1) { continue; }
        i = i + 1;
      }
    }"""
    tac = _tac(code)
    # Debe tener labels de cond y end
    assert "Lcond" in tac and "Lend" in tac
    # Debe tener gotos por break/continue
    assert tac.count("goto") >= 2

def test_for_desugars():
    code = """
    function main(){
      for (let i:integer = 0; i < 2; i = i + 1) {
        print(i);
      }
    }"""
    tac = _tac(code)
    # Debe verse el patrón de while: label cond, ifFalse ..., goto cond, label end
    assert "Lcond" in tac and "Lend" in tac
    assert "print %i" in tac or "print" in tac

def test_do_while():
    code = """
    function main(){
      let i:integer = 0;
      do { print(i); i = i + 1; } while (i < 2);
    }"""
    tac = _tac(code)
    # Debe existir label del cuerpo y salto condicional de regreso
    assert "Lbody" in tac and "Lend" in tac
    assert "if " in tac or "ifFalse " in tac