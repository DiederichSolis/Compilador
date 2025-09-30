# src/cli.py
# --- add this at the very top ---
import sys
from pathlib import Path
SRC_DIR = Path(__file__).resolve().parent  # .../Compilador/src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- then your existing imports ---
from antlr4 import FileStream, CommonTokenStream
from parsing.antlr.CompiscriptLexer import CompiscriptLexer
from parsing.antlr.CompiscriptParser import CompiscriptParser
from semantic.checker import analyze
from ir.backend.tac_generator import TacGen

def parse_file(path: str):
    """Construye el árbol sintáctico desde un archivo (.cps / .cspt)."""
    input_stream = FileStream(path, encoding="utf-8")
    lexer = CompiscriptLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    return tree, parser

def main():
    if len(sys.argv) < 2:
        print("Uso: python -m cli <archivo.cps|cspt>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Compilando {filename}...\n")

    tree, parser = parse_file(filename)

    # === SEMÁNTICA ===
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

    # === TAC SOLO SI NO HAY ERRORES ===
    has_syntax_errors = parser.getNumberOfSyntaxErrors() > 0
    has_semantic_errors = len(result["errors"]) > 0

    if not has_syntax_errors and not has_semantic_errors:
        gen = TacGen()
        gen.visit(tree)
        tac_text = gen.prog.dump(debug_addrs=True)

        print("\n=== TAC ===")
        print(tac_text)

        out_path = str(Path(filename).with_suffix(Path(filename).suffix + ".tac"))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tac_text)
        print(f"\n[TAC] Guardado en: {out_path}")
    else:
        print("\n[TAC] No generado por errores presentes.")

if __name__ == "__main__":
    main()
