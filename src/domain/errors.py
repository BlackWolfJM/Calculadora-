from dataclasses import dataclass
from typing import Optional


@dataclass
class StructuredMathError(Exception):
    code: str
    message: str
    line: int
    column: int
    end_line: int
    end_column: int
    fragment: str
    suggestion: Optional[str] = None
    internal_cause: Optional[str] = None

    def __str__(self) -> str:
        s = f"[{self.code}] {self.message} (línea {self.line}, col {self.column})"
        if self.suggestion:
            s += f". Sugerencia: {self.suggestion}"
        return s
