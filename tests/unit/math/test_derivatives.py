import pytest

from src.domain.modules.derivatives.module import DerivativesModule
from src.domain.responses import ResolutionStatus
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def test_derivatives_integration():
    """
    Prueba de integración: Parser -> SympyAdapter -> Módulo de Derivadas
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = DerivativesModule(adapter)

    # Derivada de x^2 + 3*x -> 2*x + 3
    ast = parser.parse("x^2 + 3*x")
    response = module.solve(ast, {"variable": "x", "order": 1})

    assert response.status == ResolutionStatus.SUCCESS
    assert response.calculation is not None
    assert response.calculation.primary_result is not None

    # Comprobamos que el resultado en latex incluye el 2x y el 3
    latex_res = response.calculation.primary_result.value.latex.replace(" ", "")
    assert "2x" in latex_res
    assert "3" in latex_res


def test_derivatives_trig_functions():
    """
    Prueba que la derivada de sin(x) es cos(x)
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = DerivativesModule(adapter)

    ast = parser.parse("sin(x)")
    response = module.solve(ast, {"variable": "x", "order": 1})

    assert response.status == ResolutionStatus.SUCCESS
    assert "cos" in response.calculation.primary_result.value.latex


def test_derivatives_higher_order():
    """
    Prueba que la derivada de x^3 de orden 2 es 6*x.
    También debe verificar que se produzcan dos pasos educativos (uno por derivación).
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = DerivativesModule(adapter)

    ast = parser.parse("x^3")
    response = module.solve(ast, {"variable": "x", "order": 2})

    assert response.status == ResolutionStatus.SUCCESS
    # El resultado final debería ser 6*x
    latex_res = response.calculation.primary_result.value.latex.replace(" ", "")
    assert "6x" in latex_res

    # Debe haber 2 pasos (uno para x^3 -> 3x^2 y otro para 3x^2 -> 6x)
    assert len(response.procedure.steps) == 2


def test_derivatives_validation():
    """
    Prueba la validación de parámetros de orden de derivación.
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = DerivativesModule(adapter)
    ast = parser.parse("x^2")

    with pytest.raises(ValueError, match="El orden de derivación debe ser un entero."):
        module.solve(ast, {"variable": "x", "order": "2"})

    with pytest.raises(
        ValueError, match="El orden de derivación debe estar entre 1 y 5."
    ):
        module.solve(ast, {"variable": "x", "order": 0})

    with pytest.raises(
        ValueError, match="El orden de derivación debe estar entre 1 y 5."
    ):
        module.solve(ast, {"variable": "x", "order": 6})
