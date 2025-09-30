from importlib.metadata import version

def test_antlr_runtime_and_lexer_import():
    from antlr4 import CommonTokenStream, InputStream
    from parsing.antlr.CompiscriptLexer import CompiscriptLexer
    from parsing.antlr.CompiscriptParser import CompiscriptParser

    # Verifica versión del runtime instalada (4.13.2)
    v = version("antlr4-python3-runtime")
    assert v.startswith("4.13.2")

    # Sanity: tokeniza y parsea
    code = 'const x: integer = 1; function main(){ print(1); }'
    stream = InputStream(code)
    lexer = CompiscriptLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()

    assert parser.getNumberOfSyntaxErrors() == 0
    assert tree is not None