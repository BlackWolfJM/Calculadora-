import pytest

from src.application.build_math_runtime import build_math_runtime
from src.domain.responses import ResolutionStatus
from src.presentation.structured_catalog import MODULES


@pytest.fixture(scope="module")
def runtime():
    return build_math_runtime()


@pytest.mark.parametrize(
    ("module", "operation", "expected"),
    [
        ("definite_integrals", "definite", "8/3"),
        ("vector_calculus", "divergence", "2*x + 2*y + 2*z"),
        ("vector_calculus", "curl", "(0, 0, 2)"),
        ("ode", "linear", None),
        ("matrices", "determinant", "-2"),
        ("matrices", "inverse", "[[1, -1], [-1, 2]]"),
        ("matrices", "product", "[[4], [10]]"),
        ("geometry", "circle_area", "9*pi"),
        ("geometry", "triangle_area", "6"),
        ("analytic_geometry", "distance", "5"),
        ("analytic_geometry", "midpoint", "(3, 5)"),
        ("analytic_geometry", "line", "Eq(4*x - 8, 0)"),
        ("discrete", "combinations", "120"),
        ("discrete", "permutations", "720"),
        ("discrete", "gcd", "6"),
    ],
)
def test_structured_examples(runtime, module, operation, expected):
    example = MODULES[module].operations[operation].example
    response = runtime.execute(example, module, {"operation": operation})
    assert response.status == ResolutionStatus.SUCCESS
    assert response.calculation.primary_result.value.latex
    assert response.procedure.steps
    if expected is None:
        assert response.verification == "Verificado matemáticamente con éxito."
    else:
        assert response.calculation.primary_result.value.canonical_text == expected


@pytest.mark.parametrize(
    ("module", "operation", "expression"),
    [
        ("definite_integrals", "definite", "[1/x, -1, 1]"),
        ("definite_integrals", "definite", "[sqrt(-1), 0, 1]"),
        ("vector_calculus", "curl", "[x, y]"),
        ("vector_calculus", "curl", "[x, y, t]"),
        ("ode", "linear", "[1/x, 0]"),
        ("matrices", "inverse", "[[1, 2], [2, 4]]"),
        ("matrices", "determinant", "[[1, 2], [3]]"),
        ("matrices", "product", "[[[1, 2]], [[1, 2]]]"),
        ("geometry", "triangle_area", "[2, 2, 4]"),
        ("geometry", "circle_area", "[-3]"),
        ("analytic_geometry", "line", "[[2, 1], [2, 1]]"),
        ("discrete", "combinations", "[3, 5]"),
        ("discrete", "gcd", "[1/2, 2]"),
    ],
)
def test_structured_validation(runtime, module, operation, expression):
    response = runtime.execute(expression, module, {"operation": operation})
    assert response.status == ResolutionStatus.INVALID_INPUT
    assert response.error


def test_structured_parser_keeps_scalar_mode_and_limits(runtime):
    scalar = runtime.execute("[x^2]", "derivatives", {"variable": "x"})
    assert scalar.status == ResolutionStatus.INVALID_INPUT
    excessive = "[" * 17 + "1" + "]" * 17
    response = runtime.execute(excessive, "matrices", {"operation": "determinant"})
    assert response.structured_error.code == "ERR_SECURITY_DEPTH"
