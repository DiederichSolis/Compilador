from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Union
from pathlib import Path

from antlr4 import InputStream, FileStream, CommonTokenStream, ParserRuleContext

from .error_listener import CollectingErrorListener, SyntaxDiagnostic
from .CompiscriptLexer import CompiscriptLexer
from .CompiscriptParser import CompiscriptParser

@dataclass
class ParseResult:
    """Árbol, parser, tokens y errores de sintaxis."""
    tree: ParserRuleContext
    parser: CompiscriptParser
    tokens: CommonTokenStream
    errors: list[SyntaxDiagnostic]
    def ok(self) -> bool:
        return not self.errors

def _configure(input_stream) -> Tuple[CompiscriptLexer, CompiscriptParser, CommonTokenStream, CollectingErrorListener]:
    lexer = CompiscriptLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)

    err = CollectingErrorListener()
    try:
        lexer.removeErrorListeners()
        lexer.addErrorListener(err)
    except Exception:
        pass
    parser.removeErrorListeners()
    parser.addErrorListener(err)

    return lexer, parser, tokens, err

def build_from_text(
    code: str,
    *,
    entry_rule: str = "program",
    raise_on_error: bool = False,
) -> ParseResult:
    input_stream = InputStream(code)
    _, parser, tokens, err = _configure(input_stream)

    if not hasattr(parser, entry_rule):
        raise AttributeError(f"Entry rule '{entry_rule}' no existe en CompiscriptParser.")
    rule_fn = getattr(parser, entry_rule)
    tree = rule_fn()  # type: ignore[misc]

    errors = err.errors
    if raise_on_error and errors:
        raise SyntaxError("\n".join(str(e) for e in errors))

    return ParseResult(tree=tree, parser=parser, tokens=tokens, errors=errors)

def build_from_file(
    path: Union[str, Path],
    *,
    entry_rule: str = "program",
    encoding: Optional[str] = "utf-8",
    raise_on_error: bool = False,
) -> ParseResult:
    input_stream = FileStream(str(path), encoding=encoding)
    _, parser, tokens, err = _configure(input_stream)

    if not hasattr(parser, entry_rule):
        raise AttributeError(f"Entry rule '{entry_rule}' no existe en CompiscriptParser.")
    rule_fn = getattr(parser, entry_rule)
    tree = rule_fn()  # type: ignore[misc]

    errors = err.errors
    if raise_on_error and errors:
        raise SyntaxError("\n".join(str(e) for e in errors))

    return ParseResult(tree=tree, parser=parser, tokens=tokens, errors=errors)

# Wrappers opcionales con las firmas que pediste
def build_parse_tree(source: Union[str, Path]):
    p = Path(str(source))
    res = build_from_file(p) if p.exists() else build_from_text(str(source))
    return (res.tree, res.tokens, res.parser)

def parse_from_stream(stream: InputStream):
    _, parser, tokens, _ = _configure(stream)
    tree = getattr(parser, "program")()
    return (tree, tokens, parser)
