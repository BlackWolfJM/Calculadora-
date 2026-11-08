from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """
    Rastrea el origen de un nodo AST en el texto original proporcionado
    por el estudiante. Útil para mostrar errores resaltando la posición exacta.
    """

    start: int
    end: int
    line: int = 1
    column: int = 1
    end_line: int = 1
    end_column: int = 1
