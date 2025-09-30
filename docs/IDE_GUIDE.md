# Compiscript — Guía del IDE (Streamlit)

El IDE provee una interfaz visual para editar el código, ver tokens/diagnósticos y revisar el **TAC** resultante.

## 1. Ejecutar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Inicia IDE
streamlit run src/ide/app.py
```

Abre el navegador (si no lo hace solo) en la URL local indicada por Streamlit.

## 2. Pestañas principales

- **Editor**: editor de texto con el código fuente (`.cps/.cspt`).  
  - Botón **Guardar** crea/actualiza `program/source.cps` (o el archivo activo).
- **Tokens / Parser**: lista de tokens y errores de sintaxis.
- **Diagnósticos**: errores/advertencias del **análisis semántico**.
- **Intermedio (TAC)**: muestra el **TAC** solo si no hay errores semánticos.
- **Archivos**: listado rápido de ejemplos en `program/` para abrir con un clic.

> Consejo: si no ves TAC, revisa primero **Diagnósticos** — debe estar “sin errores”.

## 3. Flujo recomendado

1. Escribe o abre un ejemplo desde **Archivos**.  
2. Pulsa **Analizar** (o *auto* al editar) para refrescar *tokens/diagnósticos*.
3. Corrige los errores hasta que **Diagnósticos** quede limpio.
4. Cambia a **Intermedio (TAC)** para ver la salida: funciones, `.locals`, labels.
5. Exporta el TAC (copiar/pegar) o usa la **CLI** para generar archivo `.tac`.

## 4. Uso por línea de comandos (CLI)

```bash
# Compilar archivo y ver diagnóstico + TAC en consola
python -m src.cli program/ejemplo.cps

# (opcional) redirigir a archivo
python -m src.cli program/ejemplo.cps > program/ejemplo.cps.tac
```

## 5. Atajos de desarrollo

- **Regenerar ANTLR** (si editas `Compiscript.g4`): ver *Makefile* (objetivo `antlr`).
- **Tests**: ejecutar pruebas unitarias bajo `src/tests/` (si están configuradas).

## 6. Errores comunes

- **No aparece TAC** → hay errores semánticos previos.
- **Imports fallan** → asegúrate de ejecutar desde la raíz del repo y que `src` esté en `PYTHONPATH` (la app ya lo hace).
- **Versiones de Python** → usa Python ≥ 3.12 como en `requirements.txt`.
