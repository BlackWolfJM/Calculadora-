import pytest

from src.domain.expressions.ast_nodes import (
    Add,
    FunctionCall,
    Multiply,
    Negate,
    NumberLiteral,
    Power,
    Symbol,
)
from src.infrastructure.parsing.parser import MathParser


@pytest.fixture
def parser():
    return MathParser()


def test_parse_number(parser):
    ast = parser.parse("42")
    assert isinstance(ast, NumberLiteral)
    assert ast.value == 42


def test_parse_addition(parser):
    ast = parser.parse("x + 5")
    assert isinstance(ast, Add)
    assert isinstance(ast.left, Symbol)
    assert ast.left.name == "x"
    assert isinstance(ast.right, NumberLiteral)
    assert ast.right.value == 5


def test_parse_implicit_multiplication(parser):
    # La gramática actual soporta multiplicación implícita mediante el token
    # IMPLICIT_MUL ('\u2062'). El preprocesador (normalizer) inyectará este token.
    # Por ahora probamos con el caracter explícito.
    ast = parser.parse("2\u2062x")
    assert isinstance(ast, Multiply)
    assert ast.implicit is True
    assert ast.left.value == 2
    assert ast.right.name == "x"


def test_parse_power_and_unary(parser):
    ast = parser.parse("-x^2")
    # Esperamos Negate(Power(x, 2)) debido a la precedencia
    assert isinstance(ast, Negate)
    assert isinstance(ast.operand, Power)
    assert ast.operand.base.name == "x"
    assert ast.operand.exponent.value == 2


def test_parse_function_call(parser):
    ast = parser.parse("sen(x)")
    assert isinstance(ast, FunctionCall)
    assert ast.name == "sin"
    assert len(ast.arguments) == 1
    assert ast.arguments[0].name == "x"


def test_parse_complex_expression(parser):
    # Probando 5*x^2/sin(x)
    ast = parser.parse("5*x^2/sin(x)")
    # La raíz debería ser Divide
    # left: Multiply(5, Power(x, 2))
    # right: FunctionCall("sin", x)
    assert ast.__class__.__name__ == "Divide"
    assert ast.left.__class__.__name__ == "Multiply"
    assert ast.left.left.value == 5
    assert ast.left.right.__class__.__name__ == "Power"
    assert ast.right.__class__.__name__ == "FunctionCall"
    assert ast.right.name == "sin"
