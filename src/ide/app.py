# app.py
from __future__ import annotations
import os, glob
import sys
from pathlib import Path
import json
import contextlib

# Rutas correctas
SRC_DIR   = Path(__file__).resolve().parents[1]   # .../Compilador/src
REPO_ROOT = SRC_DIR.parent                        # .../Compilador

# Hacer importable el paquete bajo src/
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from ir.backend.tac_generator import TacGen
from semantic.checker import analyze 
import streamlit as st
from streamlit.components.v1 import html

# Importar el builder de tu parser 
from parsing.antlr import build_from_text, ParseResult

# Intentar importar el lexer para nombres de tokens 
with contextlib.suppress(Exception):
    from parsing.antlr.CompiscriptLexer import CompiscriptLexer  

try:
    from streamlit_ace import st_ace
    HAS_ACE = True
except Exception:
    HAS_ACE = False

# ---------- Estilos CSS personalizados ----------
def inject_custom_css():
    custom_css = """
    <style>
        /* Tema oscuro similar a VSCode */
        :root {
            --primary: #1e1e1e;
            --secondary: #252526;
            --tertiary: #2d2d2d;
            --text: #d4d4d4;
            --accent: #007acc;
            --error: #f14c4c;
            --success: #4ec9b0;
            --warning: #d7ba7d;
        }
        
        /* Estilo general */
        .stApp {
            background-color: var(--primary);
            color: var(--text);
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: var(--secondary) !important;
            border-right: 1px solid #1a1a1a;
        }
        
        /* Editor */
        .ace-monokai {
            background-color: var(--primary) !important;
            border: 1px solid #1a1a1a !important;
            border-radius: 4px;
        }
        
        /* Botones */
        .stButton>button {
            border: 1px solid #1a1a1a;
            background-color: var(--tertiary);
            color: var(--text);
            transition: all 0.3s;
        }
        
        .stButton>button:hover {
            background-color: var(--accent);
            color: white;
        }
        
        /* Pestañas */
        [data-baseweb="tab-list"] {
            background-color: var(--secondary) !important;
            gap: 4px !important;
            padding: 4px !important;
        }
        
        [data-baseweb="tab"] {
            background-color: var(--tertiary) !important;
            color: var(--text) !important;
            border-radius: 4px !important;
            padding: 8px 16px !important;
            margin: 0 !important;
            border: none !important;
        }
        
        [data-baseweb="tab"][aria-selected="true"] {
            background-color: var(--accent) !important;
            color: white !important;
        }
        
        /* Terminal */
        .stCodeBlock {
            background-color: var(--secondary) !important;
            border: 1px solid #1a1a1a;
            border-radius: 4px;
        }
        
        /* Dataframes/tablas */
        .dataframe {
            background-color: var(--secondary) !important;
            color: var(--text) !important;
        }
        
        /* Títulos */
        h1, h2, h3, h4, h5, h6 {
            color: var(--text) !important;
        }
        
        /* Mensajes de estado */
        .stAlert {
            background-color: var(--tertiary) !important;
            border: 1px solid #1a1a1a !important;
        }
        
        /* Barra de herramientas del editor */
        .ace_tooltip {
            background-color: var(--secondary) !important;
            color: var(--text) !important;
            border: 1px solid #1a1a1a !important;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# ---------- Utilidades de UI ----------
@st.cache_data(show_spinner=False)
def load_examples() -> dict[str, str]:
    """
    Lee archivos de ejemplo desde program/ y src/tests/
    Devuelve { nombre_archivo: contenido }
    """
    examples: dict[str, str] = {}
    for folder in ["program", "src/tests"]:
        dir_path = REPO_ROOT / folder
        if dir_path.exists():
            for p in sorted(dir_path.iterdir()):
                if not p.is_file():
                    continue
                if p.suffix.lower() in {".cps", ".cspt", ".txt", ".code"}:
                    with contextlib.suppress(Exception):
                        # prefijo con carpeta para distinguir
                        examples[f"{folder}/{p.name}"] = p.read_text(encoding="utf-8")
    return examples

def flatten_symbols_table(symdump):
    """
    symdump puede ser:
      - dict: {"scope": "...", "entries": [ {...}, ... ]}
      - list[dict]: varios scopes con el mismo formato
    Devuelve lista de filas planas para tabla.
    """
    scopes = symdump if isinstance(symdump, list) else [symdump]
    rows = []
    for sc in scopes:
        scope_name = sc.get("scope", "")
        for e in sc.get("entries", []):
            # e viene del checker: {"name":..., "kind":..., "type": ...}
            # Aseguramos que type sea string
            etype = e.get("type")
            rows.append({
                "scope": scope_name,
                "name": e.get("name", ""),
                "kind": e.get("kind", ""),
                "type": str(etype),
            })
    return rows

def trees_to_dot(tree, parser) -> str:
    """Convierte el parse tree en DOT para visualizar con st.graphviz_chart."""
    from antlr4 import RuleContext
    from antlr4.tree.Tree import TerminalNode

    rule_names = getattr(parser, "ruleNames", None)
    counter = {"i": 0}
    lines = ["digraph G {", 'node [shape=box, fontsize=10, fontname="Consolas"];', "rankdir=TB;", 'bgcolor="transparent";']

    def nid():
        counter["i"] += 1
        return f"n{counter['i']}"

    def node_label(ctx) -> str:
        if isinstance(ctx, TerminalNode):
            tok = ctx.symbol
            txt = tok.text.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{txt}"'
        if isinstance(ctx, RuleContext):
            ridx = ctx.getRuleIndex()
            name = rule_names[ridx] if rule_names and 0 <= ridx < len(rule_names) else f"rule_{ridx}"
            return f'"{name}"'
        return '"?"'

    def walk(ctx) -> str:
        this_id = nid()
        color = "#569CD6" if isinstance(ctx, RuleContext) else "#CE9178"  # Azul para reglas, naranja para tokens
        shape = "box" if isinstance(ctx, RuleContext) else "ellipse"
        lines.append(f'{this_id} [label={node_label(ctx)}, color="{color}", fontcolor="white", fillcolor="#252526", style="filled", shape={shape}];')
        # hijos
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            child_id = walk(child)
            lines.append(f"{this_id} -> {child_id} [color=\"#7f7f7f\"];")
        return this_id

    walk(tree)
    lines.append("}")
    return "\n".join(lines)


def get_tokens_table(parse_result: ParseResult) -> list[dict]:
    """Devuelve una tabla de tokens (solo canal ON por defecto)."""
    tok_stream = parse_result.tokens
    tok_stream.fill()

    all_tokens = getattr(tok_stream, "tokens", []) or []
    on_channel = [t for t in all_tokens if getattr(t, "channel", 0) == 0]

    symbolic_names = None
    try:
        from parsing.antlr.CompiscriptLexer import CompiscriptLexer
        symbolic_names = getattr(CompiscriptLexer, "symbolicNames", None)
    except Exception:
        pass

    rows = []
    for t in on_channel:
        ttype = getattr(t, "type", None)
        if ttype == -1:
            tname = "EOF"
        elif symbolic_names and isinstance(ttype, int) and 0 <= ttype < len(symbolic_names):
            tname = symbolic_names[ttype] or str(ttype)
        else:
            tname = str(ttype)

        rows.append({
            "type": tname,
            "text": getattr(t, "text", ""),
            "line": getattr(t, "line", -1),
            "column": getattr(t, "column", -1),
        })
    return rows

# ---------- Estado inicial ----------
DEFAULT_SNIPPET = """\
const x: integer = 1;
function main() {
  print(1);
}
"""
if "ace_key" not in st.session_state:
    st.session_state.ace_key = 0

if "code" not in st.session_state:
    st.session_state.code = DEFAULT_SNIPPET
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "console" not in st.session_state:
    st.session_state.console = ""

# ---------- Layout ----------
st.set_page_config(
    page_title="Compiscript IDE",
    layout="wide",
    page_icon="🖥️",
    initial_sidebar_state="expanded"
)

# Inyectar CSS personalizado
inject_custom_css()

# Barra de título personalizada
st.markdown("""
    <div style="background-color: #1e1e1e; padding: 10px 20px; border-bottom: 1px solid #007acc; display: flex; align-items: center;">
        <h1 style="margin: 0; color: #007acc; font-size: 24px; display: flex; align-items: center;">
            <span style="margin-right: 10px;">🖥️</span>
            Compiscript IDE
        </h1>
        <div style="margin-left: auto; display: flex; gap: 10px;">
            <span style="color: #d4d4d4; font-size: 14px;">v1.0.0</span>
        </div>
    </div>
""", unsafe_allow_html=True)


# --- Helpers de carga ---



# Sidebar


# === Sidebar: carga de archivos y ejemplos ===
with st.sidebar:
    st.header("📁 Proyecto")

    # --- estado inicial para refrescar el editor ---
    if "ace_key" not in st.session_state:
        st.session_state.ace_key = 0
    if "code" not in st.session_state:
        st.session_state.code = DEFAULT_SNIPPET
    if "console" not in st.session_state:
        st.session_state.console = ""

    # --- helpers ---
    def _decode_bytes(b: bytes) -> str:
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("latin-1", errors="replace")

    def _load_uploaded_file(file):
        text = _decode_bytes(file.getvalue())
        st.session_state.code = text
        st.session_state.console = (st.session_state.get("console") or "") + f"📄 Cargado: {file.name}\n"
        st.session_state.ace_key += 1
        st.session_state["_force_compile"] = True

    # --- subir archivo ---
    uploaded = st.file_uploader(
        "Subir archivo",
        type=["cps", "cspt", "txt", "code"],
        accept_multiple_files=False,
        key="uploader",
    )
    if uploaded is not None:
        if st.session_state.get("_uploaded_name") != uploaded.name:
            text = _decode_bytes(uploaded.getvalue())
            st.session_state.code = text
            st.session_state.console = (st.session_state.get("console") or "") + f"📄 Cargado: {uploaded.name}\n"
            st.session_state["_uploaded_name"] = uploaded.name
            st.session_state["uploaded_buffer"] = {"name": uploaded.name, "text": text}  
            st.session_state.ace_key += 1
            st.session_state["_force_compile"] = True

    # --- ejemplos de program/ ---
    examples = load_examples() # dict {nombre: contenido}

    # Si hay archivo subido, lo añadimos como pseudo-ejemplo al inicio
    if "uploaded_buffer" in st.session_state:
        up = st.session_state["uploaded_buffer"]
        examples = {f"(subido) {up['name']}": up["text"], **examples}

    ex_list = ["(ninguno)"] + sorted(examples.keys())
    ex_name = st.selectbox("Ejemplos", ex_list, key="example_select")

    if ex_name != "(ninguno)":
        if st.session_state.get("_example_name") != ex_name:
            st.session_state.code = examples[ex_name]
            st.session_state.console = (st.session_state.get("console") or "") + f"📦 Ejemplo cargado: {ex_name}\n"
            st.session_state["_example_name"] = ex_name
            st.session_state.ace_key += 1
            st.session_state["_force_compile"] = True


    st.markdown("---")
    
    with st.expander("⚙️ Configuración", expanded=True):
        show_tokens = st.checkbox("Mostrar tokens", value=False, key="show_tokens")
        show_dot = st.checkbox("Mostrar AST (DOT)", value=True, key="show_dot")
        show_string_tree = st.checkbox("Mostrar árbol (texto)", value=False, key="show_string_tree")
        auto_compile = st.checkbox("Compilar automáticamente", value=False, key="auto_compile")
    
    st.markdown("---")
    st.markdown("""
        <div style="font-size: 12px; color: #7f7f7f; text-align: center;">
            Compiscript IDE v1.0.0<br>
            Desarrollado con Streamlit
        </div>
    """, unsafe_allow_html=True)

# Editor
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h2 style="margin: 0;">📝 Editor</h2>
        <div style="display: flex; gap: 10px;">
            <span style="color: #7f7f7f; font-size: 14px;">Compiscript</span>
        </div>
    </div>
""", unsafe_allow_html=True)

ace_key = st.session_state.get("ace_key", 0)

if HAS_ACE:
    code = st_ace(
        value=st.session_state.code,
        language="typescript",
        theme="monokai",
        height=350,
        key=f"ace_{ace_key}",       # <- cambia cuando cargas archivo/ejemplo
        auto_update=auto_compile,
        show_gutter=True,
        wrap=False,
        tab_size=2,
        show_print_margin=False,
        keybinding="vscode",
    )
else:
    code = st.text_area("Código fuente", value=st.session_state.code, height=300, key="code_area")

st.session_state.code = code


# --- Botones de acción (va DESPUÉS del editor, ANTES de compilar) ---
colA, colB, colC, colD = st.columns([1, 1, 1, 3])
compile_clicked = colA.button("▶️ Compilar/Analizar", use_container_width=True)
clear_console   = colB.button("🧹 Limpiar consola",   use_container_width=True)
download_code   = colC.download_button(
    "💾 Descargar código",
    data=st.session_state.code.encode("utf-8"),
    file_name="program.cps",
    mime="text/plain",
    use_container_width=True,
)
gen_tac_clicked = colD.button("🧱 Generar TAC", use_container_width=True)

if clear_console:
    st.session_state.console = ""

# ⬇️ Esto fusiona el click normal con el "force compile" que setea el uploader/ejemplos
compile_clicked = compile_clicked or st.session_state.pop("_force_compile", False)

# --- Ejecutar parsing (y lo que venga) ---
if compile_clicked or (auto_compile and st.session_state.code.strip()):
    try:
        res = build_from_text(st.session_state.code, entry_rule="program")
        st.session_state.last_result = res
        st.session_state.semantic = None
        st.session_state.tac_text = None  # resetear TAC en cada compilación

        if res.ok():
            st.session_state.console += "✅ Parse correcto.\n"
            # análisis semántico
            try:
                sem = analyze(res.tree)
                st.session_state.semantic = sem
                sem_errs = sem.get("errors", [])

                if sem_errs:
                    st.session_state.console += f"⚠️ Errores semánticos: {len(sem_errs)}\n"
                    st.session_state.console += "⛔ TAC no generado por errores semánticos.\n"
                    st.session_state.tac_text = None
                else:
                    st.session_state.console += "✅ Semántica correcta (sin errores).\n"
                    gen = TacGen()
                    gen.visit(res.tree)
                    st.session_state.tac_text = gen.prog.dump(debug_addrs=True)  # <- con direcciones
                    st.session_state.console += "🧱 TAC generado.\n"
            except Exception as ex:
                st.session_state.console += f"💥 Excepción en análisis semántico: {ex}\n"
                st.session_state.tac_text = None
        else:
            st.session_state.console += f"❌ Errores de sintaxis: {len(res.errors)}\n"
            st.session_state.console += "⛔ TAC no generado por errores de sintaxis.\n"
            st.session_state.tac_text = None
    except Exception as ex:
        st.session_state.last_result = None
        st.session_state.tac_text = None
        st.session_state.console += f"💥 Excepción: {ex}\n"

if gen_tac_clicked:
    res = st.session_state.get("last_result")
    sem = st.session_state.get("semantic")

    if not res or not res.ok():
        st.warning("Primero corrige los errores de sintaxis.")
    elif not sem or sem.get("errors"):
        st.warning("Primero corrige los errores semánticos.")
    else:
        try:
            gen = TacGen()
            gen.visit(res.tree)
            tac_text = gen.prog.dump(debug_addrs=True)
            st.session_state.tac_text = tac_text
            st.session_state.console += "🧱 TAC generado.\n"
        except Exception as ex:
            st.error(f"Error al generar TAC: {ex}")

# Consola de salida
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0 10px 0;">
        <h2 style="margin: 0;">🖥️ Consola</h2>
        <div style="display: flex; gap: 10px;">
            <span style="color: #7f7f7f; font-size: 14px;">Salida del compilador</span>
        </div>
    </div>
""", unsafe_allow_html=True)

console_placeholder = st.empty()
console_placeholder.code(st.session_state.console or "// La salida del compilador aparecerá aquí...", language="bash")

# Panel de resultados con pestañas
st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0 10px 0;">
        <h2 style="margin: 0;">📊 Resultados</h2>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["Diagnósticos", "Árbol Sintáctico", "Tokens", "Intermedio (TAC)"])

# Pestaña de diagnósticos
with tab1:
    res: ParseResult | None = st.session_state.last_result
    sem = st.session_state.get("semantic")

    if not res:
        st.info("Compila el código para ver los diagnósticos...")
    else:
        # construir tabla unificada: sintaxis + semántica
        rows = []

        # Sintaxis
        if not res.ok():
            for idx, error in enumerate(res.errors, 1):
                rows.append({
                    "Fase": "Sintaxis",
                    "#": idx,
                    "Línea": error.line,
                    "Columna": error.column,
                    "Código": "-",
                    "Mensaje": error.message,
                    "Token": getattr(error, "offending", "-"),
                })

        # Semántica (solo si hubo parse OK y tenemos resultado)
        if res.ok() and sem:
            for i, e in enumerate(sem.get("errors", []), 1):
                rows.append({
                    "Fase": "Semántica",
                    "#": i,
                    "Línea": e.get("line", -1),
                    "Columna": e.get("col", -1),
                    "Código": e.get("code", "-"),
                    "Mensaje": e.get("message", ""),
                    "Token": "-",
                })

        if not rows:
            st.success("✅ Sin errores de sintaxis ni semántica.")
        else:
            st.dataframe(
                rows,
                use_container_width=True,
                column_config={
                    "#": st.column_config.NumberColumn(width="small"),
                    "Línea": st.column_config.NumberColumn(width="small"),
                    "Columna": st.column_config.NumberColumn(width="small"),
                },
                hide_index=True
            )

        # (Opcional) ver Tabla de Símbolos
        if res.ok() and sem and sem.get("symbols"):
            with st.expander("📚 Tabla de símbolos", expanded=True):
                flat = flatten_symbols_table(sem.get("symbols", []))
                if flat:
                    st.dataframe(
                        flat,
                        use_container_width=True,
                        column_config={
                            "scope": st.column_config.TextColumn("scope", width="large"),
                            "name":  st.column_config.TextColumn("name", width="medium"),
                            "kind":  st.column_config.TextColumn("kind", width="small"),
                            "type":  st.column_config.TextColumn("type", width="small"),
                        },
                        hide_index=True,
                    )

                    # opcional: botón para ver el JSON crudo
                    if st.toggle("Ver JSON crudo", value=False):
                        st.json(sem.get("symbols", []))
                else:
                    st.info("No hay símbolos para mostrar.")

# Pestaña de árbol sintáctico
with tab2:
    res = st.session_state.last_result
    if not res or not res.ok():
        st.info("No hay árbol disponible (compila un programa válido primero).")
    else:
        tree = res.tree
        parser = res.parser

        if show_dot:
            dot = trees_to_dot(tree, parser)
            st.graphviz_chart(dot, use_container_width=True)
            
            col1, col2 = st.columns(2)
            col1.download_button(
                "Descargar DOT", 
                data=dot.encode("utf-8"),
                file_name="ast.dot", 
                mime="text/vnd.graphviz",
                use_container_width=True
            )
            
            if col2.button("Copiar DOT", use_container_width=True):
                st.session_state.dot_copy = dot
                st.toast("DOT copiado al portapapeles!", icon="📋")

        if show_string_tree:
            try:
                from antlr4.tree.Trees import Trees
                tree_text = Trees.toStringTree(tree, None, parser)
                st.code(tree_text, language="text")
            except Exception as ex:
                st.warning(f"No se pudo mostrar el árbol en formato texto: {ex}")

# Pestaña de tokens
with tab3:
    res = st.session_state.last_result
    if not res:
        st.info("Compila el código para ver los tokens...")
    else:
        if show_tokens:
            table = get_tokens_table(res)
            
            # Mostrar estadísticas
            st.info(f"Total de tokens: {len(table)}")
            
            # Tabla de tokens mejorada
            st.dataframe(
                table,
                use_container_width=True,
                column_config={
                    "line": st.column_config.NumberColumn("Línea", width="small"),
                    "column": st.column_config.NumberColumn("Columna", width="small"),
                },
                hide_index=True
            )
        else:
            st.info("Activa 'Mostrar tokens' en la configuración para ver la lista de tokens.")
with tab4:
    tac = st.session_state.get("tac_text")
    if tac:
        st.code(tac, language="text")
        st.download_button("Descargar .tac", tac.encode("utf-8"),
                           file_name="program.cps.tac", use_container_width=True)
    else:
        st.info("Compila un programa válido para ver el TAC.")