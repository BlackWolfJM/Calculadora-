from lark import Transformer, v_args

from src.domain.expressions.ast_nodes import (
    Add,
    Constant,
    Divide,
    Equals,
    FunctionCall,
    ListLiteral,
    Multiply,
    Negate,
    NumberLiteral,
    Power,
    Subtract,
    Symbol,
)
from src.domain.expressions.source_span import SourceSpan


def _span(meta) -> SourceSpan:
    return SourceSpan(
        start=meta.start_pos,
        end=meta.end_pos,
        line=meta.line,
        column=meta.column,
        end_line=meta.end_line,
        end_column=meta.end_column,
    )


@v_args(inline=True, meta=True)
class MathAstTransformer(Transformer):
    def eq(self, meta, left, eq_token, right):
        return Equals(left, right, span=_span(meta))

    def list_literal(self, meta, *items):
        return ListLiteral(items, span=_span(meta))

    def add(self, meta, left, right):
        return Add(left, right, span=_span(meta))

    def sub(self, meta, left, right):
        return Subtract(left, right, span=_span(meta))

    def mul(self, meta, left, right):
        return Multiply(left, right, implicit=False, span=_span(meta))

    def div(self, meta, left, right):
        return Divide(left, right, span=_span(meta))

    def implicit_mul(self, meta, left, implicit_token, right):
        return Multiply(left, right, implicit=True, span=_span(meta))

    def pos(self, meta, operand):
        return operand  # El más unario se puede ignorar en el AST seguro

    def neg(self, meta, operand):
        return Negate(operand, span=_span(meta))

    def pow(self, meta, base, exponent):
        return Power(base, exponent, span=_span(meta))

    def number(self, meta, n):
        n_str = str(n)
        return NumberLiteral(
            float(n_str) if "." in n_str or "e" in n_str.lower() else int(n_str),
            span=_span(meta),
        )

    def symbol(self, meta, s):
        return Symbol(str(s), span=_span(meta))

    def constant(self, meta, c):
        return Constant(str(c), span=_span(meta))

    def function_call(self, meta, name, args_tree=None):
        name_str = str(name)
        if args_tree is None:
            return FunctionCall(name_str, (), span=_span(meta))
        return FunctionCall(name_str, tuple(args_tree), span=_span(meta))

    @v_args(inline=False)
    def arguments(self, args):
        return args
