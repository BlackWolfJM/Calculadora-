import pytest

from src.application.build_math_runtime import build_math_runtime
from src.domain.responses import ResolutionStatus


@pytest.fixture
def runtime():
    """Proporciona el runtime real, usando la inicialización del proceso hijo."""
    return build_math_runtime()


def run_operation(runtime, operation, expression, **parameters):
    params = {"operation": operation}
    params.update(parameters)
    return runtime.execute(expression, "multivariable", params)


def test_multivariable_value_valid(runtime):
    result = run_operation(
        runtime,
        "multivariable_value",
        "x^2 + y^2",
        variables=["x", "y"],
        point={"x": 3, "y": 4},
    )
    assert result.status == ResolutionStatus.SUCCESS
    assert result.calculation.primary_result.value.canonical_text == "25"


def test_multivariable_value_invalid_point(runtime):
    result = run_operation(
        runtime, "multivariable_value", "x + y", variables=["x", "y"], point={"x": 3}
    )
    assert result.status == ResolutionStatus.INVALID_INPUT
    assert "asignar exactamente todas las variables" in result.error


def test_partial_valid(runtime):
    result = run_operation(runtime, "partial", "x^2 * y", variable="x", order=1)
    assert result.status == ResolutionStatus.SUCCESS
    assert result.calculation.primary_result.value.canonical_text == "2*x*y"


def test_partial_higher_order(runtime):
    result = run_operation(runtime, "partial", "x^3 * y", variable="x", order=2)
    assert result.status == ResolutionStatus.SUCCESS
    assert result.calculation.primary_result.value.canonical_text == "6*x*y"


def test_gradient_valid(runtime):
    result = run_operation(runtime, "gradient", "x^2 + y^2", variables=["x", "y"])
    assert result.status == ResolutionStatus.SUCCESS
    assert "2*x" in result.calculation.primary_result.value.canonical_text
    assert "2*y" in result.calculation.primary_result.value.canonical_text


def test_directional_valid(runtime):
    result = run_operation(
        runtime,
        "directional",
        "x^2 + y^2",
        variables=["x", "y"],
        point={"x": 1, "y": 2},
        direction=[3, 4],
    )
    assert result.status == ResolutionStatus.SUCCESS
    assert result.calculation.primary_result.value.canonical_text == "22/5"


def test_directional_zero_direction(runtime):
    result = run_operation(
        runtime,
        "directional",
        "x + y",
        variables=["x", "y"],
        point={"x": 0, "y": 0},
        direction=[0, 0],
    )
    assert result.status == ResolutionStatus.INVALID_INPUT
    assert "La dirección debe ser no nula" in result.error


def test_laplacian_valid(runtime):
    result = run_operation(runtime, "laplacian", "x^2 + y^2", variables=["x", "y"])
    assert result.status == ResolutionStatus.SUCCESS
    assert result.calculation.primary_result.value.canonical_text == "4"


def test_missing_operation(runtime):
    result = run_operation(runtime, "unknown_op", "x")
    assert result.status == ResolutionStatus.UNSUPPORTED
