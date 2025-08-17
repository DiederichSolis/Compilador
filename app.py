# app.py
from __future__ import annotations
import os
import sys
from pathlib import Path
import json
import contextlib

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Importar el builder de tu parser 
from src.parsing.antlr import build_from_text, ParseResult

# Intentar importar el lexer para nombres de tokens 
with contextlib.suppress(Exception):
    from src.parsing.antlr.CompiscriptLexer import CompiscriptLexer  


try:
    from streamlit_ace import st_ace
    HAS_ACE = True
except Exception:
    HAS_ACE = False


# ---------- Utilidades de UI ----------
def load_examples_from_program() -> dict[str, str]:
    """Lee archivos .cps/.txt del folder program/ como ejemplos."""
    examples = {}
    prog_dir = REPO_ROOT / "program"
    if prog_dir.exists():
        for p in sorted(prog_dir.glob("*")):
            if p.suffix.lower() in {".cps", ".txt", ".compis", ".cscr", ".code"} or p.name.lower() in {"program.cps"}:
                try:
                    examples[p.name] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
    return examples


def trees_to_dot(tree, parser) -> str:
    """
    Convierte el parse tree en DOT para visualizar con st.graphviz_chart.
    Muestra nombres de reglas en nodos internos y lexemas en hojas.
    """
    from antlr4 import RuleContext
    from antlr4.tree.Tree import TerminalNode

    rule_names = getattr(parser, "ruleNames", None)
    counter = {"i": 0}
    lines = ["digraph G {", 'node [shape=box, fontsize=10];', "rankdir=TB;"]

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
        lines.append(f'{this_id} [label={node_label(ctx)}];')
        # hijos
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            child_id = walk(child)
            lines.append(f"{this_id} -> {child_id};")
        return this_id

    walk(tree)
    lines.append("}")
    return "\n".join(lines)


def get_tokens_table(parse_result: ParseResult) -> list[dict]:
    """Devuelve una tabla de tokens (solo canal ON por defecto)."""
    tok_stream = parse_result.tokens
    # En Python hay que llenar explícitamente el buffer
    tok_stream.fill()

    # Lista interna de tokens (incluye ocultos; filtramos canal ON)
    all_tokens = getattr(tok_stream, "tokens", []) or []
    on_channel = [t for t in all_tokens if getattr(t, "channel", 0) == 0]

    # Nombres simbólicos (si el lexer está disponible)
    symbolic_names = None
    try:
        from src.parsing.antlr.CompiscriptLexer import CompiscriptLexer
        symbolic_names = getattr(CompiscriptLexer, "symbolicNames", None)
    except Exception:
        pass

    rows = []
    for t in on_channel:
        ttype = getattr(t, "type", None)
        # Resolver nombre del token de forma segura
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

if "code" not in st.session_state:
    st.session_state.code = DEFAULT_SNIPPET
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "console" not in st.session_state:
    st.session_state.console = ""


# ---------- Layout ----------
st.set_page_config(page_title="Compiscript IDE", layout="wide")
st.title("Compiscript IDE ")

# Sidebar
with st.sidebar:
    st.header("📁 Proyecto")
    st.caption("Carga un archivo o usa ejemplos de `program/`.")
    uploaded = st.file_uploader("Subir archivo", type=["cps", "txt", "code"], accept_multiple_files=False)
    if uploaded is not None:
        st.session_state.code = uploaded.read().decode("utf-8")

    examples = load_examples_from_program()
    if examples:
        ex_name = st.selectbox("Ejemplos de program/", ["(ninguno)"] + list(examples.keys()))
        if ex_name != "(ninguno)":
            st.session_state.code = examples[ex_name]

    st.markdown("---")
    st.header("⚙️ Opciones")
    show_tokens = st.checkbox("Mostrar tokens", value=False)
    show_dot = st.checkbox("Mostrar AST (DOT)", value=True)
    show_string_tree = st.checkbox("Mostrar árbol (string)", value=False)
    auto_compile = st.checkbox("Compilar al escribir (auto-run)", value=False)

    st.markdown("---")
    st.caption("IDE con Streamlit. Editor Ace es opcional (pip install streamlit-ace).")

# Editor
st.subheader("📝 Editor")
if HAS_ACE:
    code = st_ace(
        value=st.session_state.code,
        language="typescript",  # Compiscript no existe, usamos TS para sintaxis similar
        theme="monokai",
        height=350,
        key="ace",
        auto_update=auto_compile,
        show_gutter=True,
        wrap=False,
        tab_size=2,
    )
else:
    code = st.text_area("Código fuente", value=st.session_state.code, height=300, key="code_area")

st.session_state.code = code

# Botones de acción
colA, colB, colC, colD = st.columns([1,1,1,3])
compile_clicked = colA.button("▶️ Compilar/Analizar", use_container_width=True)
clear_console = colB.button("🧹 Limpiar consola", use_container_width=True)
download_code = colC.download_button("💾 Descargar código", data=st.session_state.code.encode("utf-8"),
                                     file_name="program.cps", mime="text/plain", use_container_width=True)

if clear_console:
    st.session_state.console = ""

# Ejecutar análisis (parsing) si se dio click o si auto
if compile_clicked or (auto_compile and code.strip()):
    try:
        res = build_from_text(st.session_state.code, entry_rule="program")
        st.session_state.last_result = res
        if res.ok():
            st.session_state.console += "✅ Parse correcto.\n"
        else:
            st.session_state.console += f"❌ Errores de sintaxis: {len(res.errors)}\n"
    except Exception as ex:
        st.session_state.last_result = None
        st.session_state.console += f"💥 Excepción: {ex}\n"

# Salida tipo “terminal”
st.subheader("🖥️ Consola / Terminal")
st.code(st.session_state.console or "(sin salida aún)")

# Panel inferior con pestañas
st.subheader("📊 Resultados")
tabs = st.tabs(["Diagnósticos", "Árbol", "Tokens"])

# Diagnósticos
with tabs[0]:
    res: ParseResult | None = st.session_state.last_result
    if not res:
        st.info("Compila para ver diagnósticos…")
    else:
        if res.ok():
            st.success("Sin errores de sintaxis.")
        else:
            st.error(f"{len(res.errors)} error(es) de sintaxis.")
            # Mostrar tabla de errores
            rows = []
            for e in res.errors:
                rows.append({
                    "line": e.line,
                    "column": e.column,
                    "token": e.offending,
                    "message": e.message,
                    "expected": e.expected,
                })
            st.dataframe(rows, use_container_width=True)

# Árbol
with tabs[1]:
    res = st.session_state.last_result
    if not res or not res.ok():
        st.info("No hay árbol disponible (o hay errores de sintaxis).")
    else:
        tree = res.tree
        parser = res.parser

        if show_dot:
            dot = trees_to_dot(tree, parser)
            st.graphviz_chart(dot, use_container_width=True)
            st.download_button("Descargar AST (DOT)", data=dot.encode("utf-8"),
                               file_name="ast.dot", mime="text/vnd.graphviz")

        if show_string_tree:
            try:
                from antlr4.tree.Trees import Trees
                st.text(Trees.toStringTree(tree, None, parser))
            except Exception as ex:
                st.warning(f"No se pudo mostrar string tree: {ex}")

# Tokens
with tabs[2]:
    res = st.session_state.last_result
    if not res:
        st.info("Compila para ver tokens…")
    else:
        if show_tokens:
            table = get_tokens_table(res)
            st.dataframe(table, use_container_width=True)
        else:
            st.info("Activa 'Mostrar tokens' en la barra lateral.")
