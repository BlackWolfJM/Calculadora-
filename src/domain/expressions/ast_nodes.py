from dataclasses import dataclass, field
from typing import Optional

from .source_span import SourceSpan


@dataclass(frozen=True)
class ExpressionNode:
    """Clase base inmutable para todos los nodos del AST matemático seguro."""

    span: Optional[SourceSpan] = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Equals(ExpressionNode):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class NumberLiteral(ExpressionNode):
    value: float | int


@dataclass(frozen=True)
class Symbol(ExpressionNode):
    name: str


@dataclass(frozen=True)
class Constant(ExpressionNode):
    name: str


@dataclass(frozen=True)
class Add(ExpressionNode):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Subtract(ExpressionNode):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Multiply(ExpressionNode):
    left: ExpressionNode
    right: ExpressionNode
    implicit: bool = False


@dataclass(frozen=True)
class Divide(ExpressionNode):
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class Power(ExpressionNode):
    base: ExpressionNode
    exponent: ExpressionNode


@dataclass(frozen=True)
class Negate(ExpressionNode):
    operand: ExpressionNode


@dataclass(frozen=True)
class FunctionCall(ExpressionNode):
    name: str
    arguments: tuple[ExpressionNode, ...]


@dataclass(frozen=True)
class ListLiteral(ExpressionNode):
    items: tuple[ExpressionNode, ...]
