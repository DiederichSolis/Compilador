# app.py
from __future__ import annotations
import os
import sys
from pathlib import Path
import json
import contextlib

import streamlit as st

# --- Resolver imports del proyecto ---
# Aseguramos que Python vea el paquete "src"
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Importar el builder de tu parser (ya lo tienes funcionando)
from src.parsing.antlr import build_from_text, ParseResult

# Intentar importar el lexer para nombres de tokens (opcional)
with contextlib.suppress(Exception):
    from src.parsing.antlr.CompiscriptLexer import CompiscriptLexer  # opcional

# Intentar usar un editor ACE si está instalado, si no: text_area
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

