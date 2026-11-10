"""Casos algebraicos y degenerados del lote vectorial 1."""

import pytest
import sympy as sp

from src.domain.modules.vector_lab import SUBTOPICS, calculate


@pytest.mark.parametrize("topic", list(SUBTOPICS))
def test_all_ten_topics_provide_a_result(topic: str) -> None:
    result = calculate(topic)
    assert result.title
    assert result.value
    assert result.steps
    assert all(step.explanation for step in result.steps)


def test_cartesian_coordinates_are_exact() -> None:
    assert calculate("01.02", (sp.Rational(1, 3), 2)).value == "[1/3, 2]"


def test_translation_preserves_vector() -> None:
    result = calculate("01.03", (3, 4), (10, 20))
    assert result.arrows[0][2] == (3.0, 4.0)
    assert result.arrows[1][1] == (10.0, 20.0)
    assert result.arrows[1][2] == (13.0, 24.0)


def test_displacement_and_distance() -> None:
    result = calculate("01.05", (1, 1), (4, 5))
    assert result.value == "[3, 4]"
    assert "5" in result.note


def test_vector_equality() -> None:
    assert calculate("01.06", (3, 2), (3, 2)).value == "Iguales"
    assert calculate("01.06", (3, 2), (3, -2)).value == "Distintos"


def test_sum_difference_and_zero() -> None:
    assert calculate("01.07", (1, 2), (3, 4)).value == "[4, 6]"
    assert calculate("01.07", (1, 2), (3, 4), operation="difference").value == "[-2, -2]"
    assert calculate("01.07", (0, 0), (0, 0)).value == "[0, 0]"


def test_negative_and_zero_scaling() -> None:
    assert calculate("01.08", (3, 4), scalar=-2).value == "[-6, -8]"
    assert calculate("01.08", (3, 4), scalar=0).value == "[0, 0]"


def test_distributivity_exactly() -> None:
    u = sp.Matrix([2, 3])
    v = sp.Matrix([4, -2])
    k = sp.Rational(3, 7)
    assert k * (u + v) == k * u + k * v
    result = calculate("01.09", list(u), list(v), scalar=k)
    assert result.value == "[6, 1]"


def test_linear_combination_and_collinearity() -> None:
    result = calculate("01.10", (1, 2), (3, 6), scalar=2)
    assert result.value == "[5, 10]"
    assert "dependientes" in result.note
    independent = calculate("01.10", (1, 0), (0, 1))
    assert "independientes" in independent.note


@pytest.mark.parametrize("a,b", [
    ((1,), (2,)), ((1, 2, 3, 4), (4, 5, 6, 7)),
    ((1, 2), (3, 4, 5)),
])
def test_invalid_dimensions(a: tuple[int, ...], b: tuple[int, ...]) -> None:
    with pytest.raises(ValueError):
        calculate("01.07", a, b)


def test_nonreal_and_nonfinite_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        calculate("01.07", (sp.I, 1), (2, 3))
    with pytest.raises(ValueError):
        calculate("01.08", (2, 3), scalar=sp.oo)


def test_3d_algebra_is_preserved() -> None:
    result = calculate("01.07", (1, 2, 3), (4, 5, 6))
    assert result.value == "[5, 7, 9]"
    assert result.arrows[2][2] == (5.0, 7.0)


def test_unsupported_operation_and_subtopic() -> None:
    with pytest.raises(ValueError):
        calculate("01.07", operation="multiply")
    with pytest.raises(ValueError):
        calculate("99.99")
