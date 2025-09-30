# Compiscript – Fase TAC ✅

Proyecto de compilador educativo para **Compiscript** (subset de TypeScript) con:
- Gramática ANTLR4 (Python target)
- **Análisis semántico** (tabla de símbolos + validaciones)
- **Generación de TAC** (Three Address Code) con *peephole* simple
- **IDE** en Streamlit (editor, AST DOT, tokens, diagnósticos, TAC)

## 🚀 Cómo correr

### 1) Instalar
```bash
python -m venv .venv && source .venv/bin/activate  # en macOS/Linux
# En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Pruebas
```bash
pytest -q
# Esperado: 18 passed
```

### 3) CLI
```bash
PYTHONPATH=src python -m src.cli program/program.cps
# Genera program/program.cps.tac si no hay errores
```

### 4) IDE
```bash
streamlit run src/ide/app.py
```
En la pestaña **Intermedio (TAC)** verás el TAC **solo si** no hay errores de sintaxis/semántica.

## 🧱 TAC en 1 minuto
- Temporales: `tN`
- Locales: `%name`
- Globales/const: `@NAME` (si aplica)
- Literales: `#5`, `#"hola"`, `#3.0`
- Estructuras: `label`, `goto`, `if`/`ifFalse`, `param`, `call`, `ret`
- Arrays/objetos: `newarr`, `aload`, `astore`, `new`, `getf`, `setf`
- IO: `print`

Más detalle en [`docs/TAC_SPEC.md`](docs/TAC_SPEC.md).

## 📁 Estructura
```
src/
  parsing/ … (ANTLR + builder)
  semantic/ … (checker, tabla de símbolos)
  ir/tac/ … (instructions, emitter, program)
  ir/backend/tac_generator.py
  ide/app.py
docs/
  ARCHITECTURE.md  IDE_GUIDE.md  SEMANTIC_RULES.md  TAC_SPEC.md
program/program.cps  # ejemplo
```

## 🧪 Cobertura mínima de tests
- Expresiones aritméticas/unarias
- AND/OR corto-circuito, ternario
- Asignaciones y variables
- `if/else`, `while`, `do-while`, `for`, `break/continue`
- Arreglos (`newarr/aload/astore`), llamadas y retorno
- `switch` y `try/catch` (shape estructural)

## 🏷️ Licencia
MIT