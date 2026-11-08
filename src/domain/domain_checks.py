"""Validate original AST subexpressions before algebraic cancellation."""

from dataclasses import fields, is_dataclass

import sympy as sp

from src.domain.expressions.ast_nodes import Divide, ExpressionNode


def nodes(node):
    yield node
    if is_dataclass(node):
        for field in fields(node):
            value = getattr(node, field.name)
            if isinstance(value, ExpressionNode):
                yield from nodes(value)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    if isinstance(child, ExpressionNode):
                        yield from nodes(child)


def require_real_finite(value):
    if value.is_real is not True or value.is_finite is not True:
        raise ValueError(
            "No se pudo confirmar un valor real finito en el punto indicado."
        )


def validate_point(ast, substitutions, adapter):
    for node in nodes(ast):
        value = adapter.ast_to_sympy(node).subs(substitutions, simultaneous=True)
        require_real_finite(value)
        if isinstance(node, Divide):
            denominator = adapter.ast_to_sympy(node.right).subs(substitutions)
            if denominator.is_zero is not False:
                raise ValueError(
                    "El punto anula un denominador de la expresión original."
                )


def real_domain(ast, variable, adapter):
    domain = sp.S.Reals
    for node in nodes(ast):
        expr = adapter.ast_to_sympy(node)
        if isinstance(expr, sp.Expr):
            domain = domain.intersect(
                sp.calculus.util.continuous_domain(expr, variable, sp.S.Reals)
            )
        if isinstance(node, Divide):
            zeros = sp.solveset(
                adapter.ast_to_sympy(node.right), variable, domain=sp.S.Reals
            )
            domain = domain - zeros
    return domain
