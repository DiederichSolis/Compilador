# src/tests/test_examples.py
import os
from antlr4 import FileStream, CommonTokenStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from semantic.checker import analyze

BASE = os.path.dirname(__file__)  # mismo directorio (src/tests)

OK = [
    "Ejemplo1.cspt",
    "Ejemplo2.cspt",
    "Ejemplo3.cspt",
    "Ejemplo4.cspt",
    "Ejemplo5.cspt",
    "Ejemplo6.cspt",
]
FAIL = [
    
]

def compile_file(path):
    input_stream = FileStream(path, encoding="utf-8")
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    tree = parser.program()
    return analyze(tree)

def test_examples_ok():
    for fname in OK:
        path = os.path.join(BASE, fname)
        assert os.path.exists(path), f"No existe {path}"
        res = compile_file(path)
        assert res["errors"] == [], f"{fname} no debería dar errores, obtuvo: {res['errors']}"

def test_examples_fail():
    for fname in FAIL:
        path = os.path.join(BASE, fname)
        assert os.path.exists(path), f"No existe {path}"
        res = compile_file(path)
        assert res["errors"], f"{fname} debería dar errores semánticos"