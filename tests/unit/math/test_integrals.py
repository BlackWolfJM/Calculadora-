from src.domain.modules.integrals.module import IntegralsModule
from src.domain.responses import ResolutionStatus
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def test_integral_unevaluated():
    """
    Prueba que una integral sin antiderivada cerrada devuelve UNEVALUATED
    sin agregar '+ C'.
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = IntegralsModule(adapter)

    ast = parser.parse("sin(x^x)")
    response = module.solve(ast, {"variable": "x"})

    assert response.status == ResolutionStatus.UNEVALUATED
    assert "+ C" not in response.calculation.primary_result.value.canonical_text
    assert "No se encontró una antiderivada cerrada" in response.warnings[0]


def test_integral_evaluated():
    """
    Prueba que una integral resuelta devuelve SUCCESS con '+ C'.
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = IntegralsModule(adapter)

    ast = parser.parse("x^2")
    response = module.solve(ast, {"variable": "x"})

    assert response.status == ResolutionStatus.SUCCESS
    text_res = response.calculation.primary_result.value.canonical_text
    assert "+ C" in text_res
    assert "x**3/3" in text_res
