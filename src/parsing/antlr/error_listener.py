from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from antlr4.error.ErrorListener import ErrorListener

@dataclass(frozen=True)
class SyntaxDiagnostic:
    line: int
    column: int
    offending: Optional[str]
    message: str
    expected: Optional[str] = None
    rule_stack: Optional[str] = None

    def __str__(self) -> str:
        at = f"(l{self.line}, c{self.column})"
        tok = f" token='{self.offending}'" if self.offending is not None else ""
        exp = f" expected={self.expected}" if self.expected else ""
        return f"[SyntaxError]{at}{tok}: {self.message}{exp}"

class CollectingErrorListener(ErrorListener):
    def __init__(self) -> None:
        super().__init__()
        self._errors: List[SyntaxDiagnostic] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        expected = None
        rule_stack = None
        try:
            if e is not None and hasattr(e, "getExpectedTokens"):
                expected = e.getExpectedTokens().toString(
                    recognizer.literalNames, recognizer.symbolicNames
                )
            if recognizer is not None and hasattr(recognizer, "getRuleInvocationStack"):
                stack = recognizer.getRuleInvocationStack()
                rule_stack = " > ".join(stack) if stack else None
        except Exception:
            pass

        offending_text = getattr(offendingSymbol, "text", None)
        self._errors.append(
            SyntaxDiagnostic(
                line=line,
                column=column,
                offending=offending_text,
                message=msg,
                expected=expected,
                rule_stack=rule_stack,
            )
        )

    @property
    def errors(self) -> List[SyntaxDiagnostic]:
        return list(self._errors)

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def clear(self) -> None:
        self._errors.clear()
