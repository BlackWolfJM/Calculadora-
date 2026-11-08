import pytest
import sympy as sp

from src.application.build_math_runtime import build_math_runtime
from src.domain.errors import StructuredMathError
from src.domain.responses import ResolutionStatus
from src.infrastructure.parsing.parser import MathParser


@pytest.mark.parametrize(
    "expression,operation",
    [
        ("x/x", "multivariable_value"),
        ("1/x", "directional"),
        ("abs(x)", "directional"),
    ],
)
def test_invalid_points_are_not_success(expression, operation):
    result = build_math_runtime().execute(
        expression,
        "multivariable",
        {
            "operation": operation,
            "variables": ["x", "y"],
            "point": {"x": 0, "y": 0},
            "direction": [1, 0],
        },
    )
    assert result.status is ResolutionStatus.INVALID_INPUT


def test_verifier_preserves_other_real_symbols():
    result = build_math_runtime().execute("x*y", "derivatives", {"variable": "x"})
    assert result.status is ResolutionStatus.SUCCESS
    assert result.verification == "Verificado matemáticamente con éxito."


@pytest.mark.parametrize("expression", ["x=x", "sin(x)=0"])
def test_infinite_equations_do_not_say_no_solutions(expression):
    result = build_math_runtime().execute(expression, "equations", {"variable": "x"})
    assert result.status is ResolutionStatus.SUCCESS
    assert "Sin solución" not in result.procedure.steps[0].after_latex


def test_equation_preserves_excluded_zero():
    result = build_math_runtime().execute("x/x=1", "equations", {"variable": "x"})
    assert (
        "Todos los números reales"
        not in result.calculation.primary_result.value.canonical_text
    )
    assert result.status is ResolutionStatus.SUCCESS


@pytest.mark.parametrize("text", ["1e3*x", "x(x+1)", "(x+1)(x-1)", "x^(1^11)"])
def test_parser_supported_notations(text):
    assert MathParser().parse(text)


@pytest.mark.parametrize("text", ["sin()", "x^(abs(101))"])
def test_parser_rejects_invalid_arity_and_exponent(text):
    with pytest.raises(StructuredMathError):
        MathParser().parse(text)


def test_source_map_uses_original_position():
    with pytest.raises(StructuredMathError) as info:
        MathParser().parse("2x+&")
    assert info.value.column == 4


def test_directional_polynomial_limit():
    result = build_math_runtime().execute(
        "x^2+y^2",
        "multivariable",
        {
            "operation": "directional",
            "variables": ["x", "y"],
            "point": {"x": 1, "y": 2},
            "direction": [3, 4],
        },
    )
    assert result.status is ResolutionStatus.SUCCESS
    assert sp.sympify(
        result.calculation.primary_result.value.canonical_text
    ) == sp.Rational(22, 5)
