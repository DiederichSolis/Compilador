# src/cli.py
import sys
from antlr4 import FileStream, CommonTokenStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from semantic.checker import analyze

def parse_file(path: str):
    """Construye el árbol sintáctico desde un archivo .cps"""
    input_stream = FileStream(path, encoding="utf-8")
    lexer = CompiscriptLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()   # regla inicial de tu gramática
    return tree

def main():
    if len(sys.argv) < 2:
        print("Uso: python -m cli <archivo.cps>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Compilando {filename}...\n")

    tree = parse_file(filename)
    result = analyze(tree)

    print("=== Tabla de símbolos ===")
    for sym in result["symbols"]:
        print(sym)

    print("\n=== Errores ===")
    if not result["errors"]:
        print("Sin errores ✅")
    else:
        for e in result["errors"]:
            print(f"{e['line']}:{e['col']} {e['code']}: {e['message']}")

if __name__ == "__main__":
    main()
