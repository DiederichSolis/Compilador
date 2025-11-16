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
        print("Uso: python -m cli <archivo.cps|cspt> [opciones]")
        print("Opciones:")
        print("  --no-optimize    Desactivar optimizaciones TAC")
        print("  --compare        Mostrar comparación entre código optimizado y no optimizado")
        print("  --no-mips        No generar código MIPS")
        print("  --mips-only      Solo generar código MIPS (sin mostrar TAC)")
        print("  --functional     Generar código MIPS funcional completo (con salida real)")
        sys.exit(1)

    # Procesar argumentos
    filename = None
    optimize = True
    show_comparison = False
    generate_mips = True
    mips_only = False
    functional_mips = False
    
    # Buscar el archivo y procesar opciones
    for arg in sys.argv[1:]:
        if arg == "--no-optimize":
            optimize = False
        elif arg == "--compare":
            show_comparison = True
        elif arg == "--no-mips":
            generate_mips = False
        elif arg == "--mips-only":
            mips_only = True
        elif arg == "--functional":
            functional_mips = True
        elif not arg.startswith("--"):
            filename = arg
    
    if not filename:
        print("Error: Debes especificar un archivo .cps o .cspt")
        sys.exit(1)
    
    print(f"Compilando {filename}{'... (sin optimizaciones)' if not optimize else '... (con optimizaciones)'}\n")

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
        
        if show_comparison:
            # Mostrar comparación de optimización
            print("\n=== TAC SIN OPTIMIZAR ===")
            tac_unoptimized = gen.prog.dump(debug_addrs=True, optimize=False)
            print(tac_unoptimized)
            
            print("\n=== TAC OPTIMIZADO ===")
            tac_optimized = gen.prog.dump(debug_addrs=True, optimize=True)
            print(tac_optimized)

            # Guardar ambas versiones si se está comparando
            out_path_unopt = str(Path(filename).with_suffix(Path(filename).suffix + ".unopt.tac"))
            with open(out_path_unopt, "w", encoding="utf-8") as f:
                f.write(tac_unoptimized)
            
            out_path_opt = str(Path(filename).with_suffix(Path(filename).suffix + ".tac"))
            with open(out_path_opt, "w", encoding="utf-8") as f:
                f.write(tac_optimized)
                
            print(f"\n[TAC] Sin optimizar guardado en: {out_path_unopt}")
            print(f"[TAC] Optimizado guardado en: {out_path_opt}")
            
            # Generar código MIPS del optimizado si se solicita
            if generate_mips:
                try:
                    from ir.backend.mips.simple_generator import SimpleMipsGenerator
                    mips_gen = SimpleMipsGenerator()
                    optimized_prog = gen.prog.get_optimized()
                    mips_code = mips_gen.generate_program(optimized_prog)
                    
                    print(f"\n=== CÓDIGO MIPS ===")
                    print(mips_code)
                    
                    # Guardar código MIPS
                    mips_path = str(Path(filename).with_suffix(Path(filename).suffix + ".s"))
                    with open(mips_path, "w", encoding="utf-8") as f:
                        f.write(mips_code)
                    
                    print(f"\n[MIPS] Código MIPS guardado en: {mips_path}")
                    
                except Exception as ex:
                    print(f"\n[MIPS] Error al generar código MIPS: {ex}")
                    import traceback
                    traceback.print_exc()
        else:
            # Solo generar la versión solicitada
            if not mips_only:
                tac_text = gen.prog.dump(debug_addrs=True, optimize=optimize)
                
                print(f"\n=== TAC {'OPTIMIZADO' if optimize else 'SIN OPTIMIZAR'} ===")
                print(tac_text)

                # Guardar solo la versión solicitada
                suffix = ".tac" if optimize else ".unopt.tac"
                out_path = str(Path(filename).with_suffix(Path(filename).suffix + suffix))
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(tac_text)
                    
                opt_status = "optimizado" if optimize else "sin optimizar"
                print(f"\n[TAC] Código {opt_status} guardado en: {out_path}")
            
            # Generar código MIPS si se solicita
            if generate_mips:
                try:
                    if functional_mips:
                        from ir.backend.mips.functional_generator import FunctionalMipsGenerator
                        mips_gen = FunctionalMipsGenerator()
                        # Para el generador funcional, no necesitamos el TAC específico
                        mips_code = mips_gen.generate_program(gen.prog)
                        print(f"\n=== CÓDIGO MIPS FUNCIONAL ===")
                        print(mips_code)
                        
                        # Guardar código MIPS funcional
                        mips_path = str(Path(filename).with_suffix(Path(filename).suffix + ".functional.s"))
                        with open(mips_path, "w", encoding="utf-8") as f:
                            f.write(mips_code)
                        print(f"\n[MIPS] Código MIPS funcional guardado en: {mips_path}")
                    else:
                        from ir.backend.mips.simple_generator import SimpleMipsGenerator
                        mips_gen = SimpleMipsGenerator()
                        # Usar el programa optimizado para generar MIPS
                        optimized_prog = gen.prog.get_optimized() if optimize else gen.prog
                        mips_code = mips_gen.generate_program(optimized_prog)
                        
                        print(f"\n=== CÓDIGO MIPS {'(OPTIMIZADO)' if optimize else '(SIN OPTIMIZAR)'} ===")
                        print(mips_code)
                        
                        # Guardar código MIPS
                        mips_suffix = ".s" if optimize else ".unopt.s"
                        mips_path = str(Path(filename).with_suffix(Path(filename).suffix + mips_suffix))
                        with open(mips_path, "w", encoding="utf-8") as f:
                            f.write(mips_code)
                        
                        opt_status = "optimizado" if optimize else "sin optimizar"
                        print(f"\n[MIPS] Código MIPS {opt_status} guardado en: {mips_path}")
                    
                except Exception as ex:
                    print(f"\n[MIPS] Error al generar código MIPS: {ex}")
                    import traceback
                    traceback.print_exc()
    else:
        print("\n[TAC] No generado por errores presentes.")

if __name__ == "__main__":
    main()