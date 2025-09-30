# Compiscript — Arquitectura del Compilador

> **Resumen:** Este proyecto implementa un compilador educativo para **Compiscript** (subset de TypeScript) en Python con ANTLR4. La tubería incluye: *parseo → análisis semántico → IR (TAC) → visualización IDE*. El foco actual es el **TAC**.

## 1. Estructura de carpetas

```
Compilador/
├─ Compiscript.g4               # Gramática ANTLR4
├─ requirements.txt             # Dependencias (antlr4-python3-runtime, streamlit, etc.)
├─ Makefile                     # Atajos (generar ANTLR, tests)
├─ program/                     # Ejemplos de entrada/salida (.cps/.cspt/.tac)
├─ src/
│  ├─ cli.py                    # CLI: compilar archivo y emitir TAC/diagnósticos
│  ├─ ide/                      # IDE en Streamlit
│  │  └─ app.py
│  ├─ parsing/
│  │  ├─ antlr/                 # Artefactos generados por ANTLR
│  │  │  ├─ CompiscriptLexer.py
│  │  │  ├─ CompiscriptParser.py
│  │  │  └─ CompiscriptVisitor.py
│  ├─ semantic/                 # Análisis semántico
│  │  ├─ checker.py             # Recorrido + validaciones
│  │  ├─ diagnostics.py         # Recolección de errores/advertencias
│  │  ├─ symbol_table.py        # Pila de scopes
│  │  ├─ symbols.py             # Símbolos (variables, funciones, clases, params)
│  │  └─ types.py               # Tipos: Int, Float, Bool, String, Null, Void, Array, Class
│  └─ ir/
│     ├─ backend/
│     │  └─ tac_generator.py    # Visitor que emite TAC desde el AST
│     └─ tac/                   # Infraestructura TAC
│        ├─ program.py          # TacProgram/TacFunction, .dump()
│        ├─ emitter.py          # Azúcar para emitir instrucciones/labels
│        └─ instructions.py     # Instrucciones TAC (Binary, Unary, Move, Goto, Call, Ret, …)
└─ docs/
   ├─ ARCHITECTURE.md
   ├─ IDE_GUIDE.md
   ├─ SEMANTIC_RULES.md
   └─ TAC_SPEC.md
```

## 2. Flujo de compilación

1) **Léxico/Sintaxis (ANTLR4)**
   - `Compiscript.g4` define tokens y reglas.  
   - ANTLR genera *Lexer/Parser/Visitor* en `src/parsing/antlr/`.

2) **AST + *Visitor***
   - Se usa `CompiscriptVisitor` para recorrer el *parse tree*.
   - No se construye AST explícito separado; los *visitors* operan sobre el *parse tree* del parser.

3) **Análisis semántico** (`src/semantic/`)
   - `checker.py` recorre el árbol:
     - **Tabla de símbolos** con pila de *scopes* (global, función, clase, bloque).
     - **Resolución de identificadores** y **tipado** (operaciones, llamadas, retornos).
     - Reglas descritas en `docs/SEMANTIC_RULES.md`.
   - Los diagnósticos se agregan en `diagnostics.py`.

4) **IR TAC / Código intermedio** (`src/ir/`)
   - `backend/tac_generator.py` emite instrucciones en forma de **TAC**:
     - Operandos: temporales `tN`, locales `%x`, globales `@g`, literales `#5`, `#"txt"`.
     - Control de flujo: `label`, `goto`, `if_goto`, `if_false`.
     - Llamadas: `param`, `call`, `ret`.
     - Objetos/Arreglos: `new`, `getf`, `setf`, `newarr`, `aload`, `astore`.
     - Utilidades: `print`.
   - `tac_generator` aplica un *peephole* básico (p.ej., elimina `goto L` seguido de `L:`).

5) **Salida**
   - `TacProgram.dump()` serializa a texto legible con encabezados por función:
     ```
     .func nombre(a, b) : Int
       .locals 3
       t0 = %a + %b
       ret t0
     .endfunc
     ```
   - La IDE muestra TAC si no hay errores semánticos.

## 3. Entradas y formatos soportados

- **Fuente**: `.cps` / `.cspt` (dialecto tipo TypeScript).
- **Unidades**: programa monolítico con declaraciones (variables/constantes, funciones, clases) y *statements* (asignaciones, if/while/do/for, print, exprs).
- **Tipos**: `Int`, `Float`, `Bool`, `String`, `Null`, `Void`, `Array<T>`, `Class` (básico).

## 4. Componentes claves

- **`symbol_table.py`**: pila de *scopes* encadenados con *lookup* ascendente.  
- **`symbols.py`**: `VariableSymbol`, `FunctionSymbol`, `ClassSymbol`, `ParamSymbol`.  
- **`types.py`**: tipos primitivos y agregados (`ArrayType`, `ClassType`).  
- **`checker.py`**: comprobaciones de tipado, retornos, visibilidad, *const*, aridad.  
- **`tac_generator.py`**: *visitor* que convierte nodos del parser a TAC usando `Emitter`.  
- **`emitter.py`**: genera temporales/labels y agrega instrucciones a `TacFunction`.  
- **`instructions.py`**: define clases de instrucción y su representación string.  

## 5. Extensibilidad

- **Nuevos tipos**: ampliar `types.py` y reglas en `checker.py` y `tac_generator.py`.
- **Optimización**: agregar *passes* antes de `TacProgram.dump()`.
- **Backends**: implementar traductor TAC→ASM/LLVM/WASM en `ir/backend/`.
- **IDE**: añadir pestañas (CFG, SSA, *live ranges*).

## 6. Dependencias

- Python 3.12+
- `antlr4-python3-runtime`
- `streamlit`
- (Opcional) `graphviz` si agregas visualización de AST/CFG.
