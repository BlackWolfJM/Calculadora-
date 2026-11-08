import pytest
import sympy as sp

from src.application.build_math_runtime import build_math_runtime
from src.domain.modules.matrices import OPERATIONS
from src.domain.responses import ResolutionStatus
from src.infrastructure.calculation_worker import (
    deserialize_response,
    serialize_response,
)
from src.infrastructure.parsing.matrix_parser import (
    MatrixEvaluator,
    as_matrix,
    parse_matrix_input,
)
from src.presentation.structured_catalog import MATRIX_OPERATIONS


@pytest.fixture(scope="module")
def solve():
    runtime = build_math_runtime()

    def run(operation, expression, **parameters):
        return runtime.execute(
            expression, "matrices", {"operation": operation, **parameters}
        )

    return run


def text(answer):
    assert answer.status in (
        ResolutionStatus.SUCCESS,
        ResolutionStatus.SUCCESS_WITH_WARNINGS,
    )
    assert answer.procedure.steps
    return answer.calculation.primary_result.value.canonical_text


def matrix(value):
    return as_matrix(MatrixEvaluator(parse_matrix_input(value)).evaluate())


@pytest.mark.parametrize("operation", MATRIX_OPERATIONS)
def test_every_catalog_example(solve, operation):
    assert set(MATRIX_OPERATIONS) == OPERATIONS
    response = solve(
        operation,
        MATRIX_OPERATIONS[operation].example,
        A="[[1,2],[3,4]]",
        B="[[5,6],[7,8]]",
    )
    assert text(response)


@pytest.mark.parametrize(
    ("method", "index"),
    [("auto", 1), ("row", 2), ("column", 3), ("elimination", 1)],
)
def test_determinant_methods_with_zero_pivot(solve, method, index):
    value = "[[0,2,1],[1,-1,2],[3,1,0]]"
    assert text(solve("determinant", value, method=method, index=index)) == "16"


@pytest.mark.parametrize("operation", ["gauss", "inverse_system", "cramer"])
def test_multiple_right_hand_sides(solve, operation):
    a, b = "[[2,1],[1,-1]]", "[[5,4],[1,2]]"
    response = solve(operation, f"[{a}, {b}]")
    assert matrix(a) * matrix(text(response)) == matrix(b)
    assert response.verification


def test_classifies_underdetermined_and_inconsistent_systems(solve):
    a = "[[1,2,3],[2,4,6]]"
    assert text(solve("compatibility", f"[{a},[[4],[8]]]")) == "Infinitas soluciones"
    solution = matrix(text(solve("gauss", f"[{a},[[4],[8]]]")))
    assert (
        (matrix(a) * solution - sp.Matrix([4, 8])).applyfunc(sp.simplify).is_zero_matrix
    )
    assert len(solution.free_symbols) == 2
    assert text(solve("gauss", f"[{a},[[4],[9]]]")) == "Sin solución"


def test_factorizations_reconstruct_input_after_worker_roundtrip(solve):
    examples = {
        "lu": "[[0,2,3],[3,4,1]]",
        "cholesky": "[[3,i],[-i,3]]",
        "svd": "[[3,0,0],[0,2,0]]",
        "jordan": "[[2,1],[0,2]]",
        "diagonalize": "[[2,1],[1,2]]",
    }
    for operation, source in examples.items():
        answer = deserialize_response(serialize_response(solve(operation, source)))
        assert text(answer)
        assert answer.verification
        factors = [
            matrix(item.value.canonical_text)
            for item in answer.calculation.related_results
        ]
        a = matrix(source)
        if operation == "lu":
            p, lower, upper = factors
            assert p * a == lower * upper
        elif operation == "cholesky":
            lower, adjoint = factors
            assert adjoint == lower.H
            assert (a - lower * adjoint).applyfunc(sp.simplify).is_zero_matrix
        elif operation == "svd":
            u, s, v = factors
            assert a == u * s * v.H
        else:
            p, diagonal = factors
            assert a * p == p * diagonal


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2A + 3B", "[[17, 22], [27, 32]]"),
        ("determinant({{1/3,0},{0,3}})", "1"),
        ("AX=B", "[[-3, -4], [4, 5]]"),
        ("Y+A=B", "[[4, 4], [4, 4]]"),
        ("{{0.1(6),sin(30deg),3!}}", "[[1/6, 1/2, 6]]"),
        ("{{i,2}}^{*}", "[[-i], [2]]"),
        ("{{1,0},{0,1/2}}^∞", "[[1, 0], [0, 0]]"),
        ("{{2,0},{0,3}}^n", "[[2**n, 0], [0, 3**n]]"),
        ("1/3 < 1/2", "Verdadero"),
    ],
)
def test_exact_matrix_expression(solve, expression, expected):
    response = solve("expression", expression, A="[[1,2],[3,4]]", B="[[5,6],[7,8]]")
    assert text(response) == expected


def test_precision_only_changes_display(solve):
    result = solve("scale", "[[[1,2]],1/3]", precision=5)
    assert text(result) == "[[1/3, 2/3]]"
    assert "0.33333" in result.calculation.primary_result.value.latex


@pytest.mark.parametrize(
    ("operation", "expression"),
    [
        ("inverse", "[[1,2],[2,4]]"),
        ("cholesky", "[[1,2],[2,1]]"),
        ("product", "[[[1,2]],[[3,4]]]"),
        ("power", "[[[2]],infinity]"),
        ("determinant", "[[1],[2,3]]"),
        ("expression", "__import__('os')"),
        ("expression", "A.__class__"),
        ("expression", "[x for x in A]"),
        ("expression", "10^(10^100)"),
        ("expression", "1e100000"),
    ],
)
def test_invalid_operations_are_predictable(solve, operation, expression):
    answer = solve(operation, expression)
    assert answer.status == ResolutionStatus.INVALID_INPUT
    assert answer.error
