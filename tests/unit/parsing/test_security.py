import pytest

from src.domain.errors import StructuredMathError
from src.infrastructure.parsing.parser import MathParser


def test_security_depth_limit():
    parser = MathParser()

    # Construimos una expresión muy anidada (ej. (((((x^2)^2)^2)^2)...)
    depth = 20
    expr = "x"
    for _ in range(depth):
        expr = f"({expr}^2)"

    with pytest.raises(StructuredMathError) as exc_info:
        parser.parse(expr)

    assert exc_info.value.code == "ERR_SECURITY_DEPTH"


def test_security_node_limit():
    parser = MathParser()
    parser.security.max_depth = 100  # Evitar que salte el límite de profundidad primero

    # Construimos una expresión con muchos nodos (ej. x+x+x+x+...)
    # 60 sumandos superan el límite de 50
    expr = "+".join(["x"] * 60)

    with pytest.raises(StructuredMathError) as exc_info:
        parser.parse(expr)

    assert exc_info.value.code == "ERR_SECURITY_NODES"


def test_security_exponent_limit():
    parser = MathParser()

    # Exponente gigantesco
    expr = "x^999999999"
    with pytest.raises(StructuredMathError) as exc_info:
        parser.parse(expr)
    assert exc_info.value.code == "ERR_SECURITY_EXPONENT"

    # Exponente compuesto permitido
    expr2 = "x^(50+50)"
    ast2 = parser.parse(expr2)
    assert ast2 is not None

    # Exponente compuesto denegado
    expr3 = "x^(50+51)"
    with pytest.raises(StructuredMathError) as exc_info3:
        parser.parse(expr3)
    assert exc_info3.value.code == "ERR_SECURITY_EXPONENT"

    # Exponente con división por cero
    expr4 = "x^(1/0)"
    with pytest.raises(StructuredMathError) as exc_info4:
        parser.parse(expr4)
    assert exc_info4.value.code == "ERR_DIVISION_BY_ZERO"


def test_security_valid_expression_passes():
    parser = MathParser()

    # Expresión razonable
    expr = "sin(x^2) + 5*x"

    # No debería lanzar excepción
    ast = parser.parse(expr)
    assert ast is not None
