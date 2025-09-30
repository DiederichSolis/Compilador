def test_semantic_minimal_program_no_errors():
    from antlr4 import CommonTokenStream, InputStream
    from parsing.antlr.CompiscriptLexer import CompiscriptLexer
    from parsing.antlr.CompiscriptParser import CompiscriptParser
    from semantic.checker import analyze

    code = 'const x: integer = 1; function main(){ print(1); }'
    stream = InputStream(code)
    lexer = CompiscriptLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    res = analyze(tree)
    assert parser.getNumberOfSyntaxErrors() == 0
    assert not res.get("errors"), res.get("errors")