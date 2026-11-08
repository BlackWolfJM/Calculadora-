from src.domain.modules.derivatives.module import DerivativesModule
from src.domain.steps import StepCoverage
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def test_derivative_steps_generation():
    """
    Prueba que el motor de pasos determinista genera una traza recursiva
    correcta para sumas y potencias sin usar IA generativa.
    """
    parser = MathParser()
    adapter = SympyAdapter()
    module = DerivativesModule(adapter)

    # Derivada de x^2 + x -> 2x + 1
    ast = parser.parse("x^2 + x")
    response = module.solve(ast, {"variable": "x", "order": 1})

    # Validar que los pasos se generaron con cobertura completa
    assert response.procedure is not None
    assert response.procedure.coverage == StepCoverage.COMPLETE

    # La raíz del árbol de pasos debe ser la Regla de la Suma
    # (porque x^2 + x es una suma)
    root_step = response.procedure.steps[0]
    assert "suma" in root_step.rule_name.lower()

    # Debe tener dos subpasos (uno para x^2 y uno para x)
    assert len(root_step.sub_steps) == 2

    # SymPy ordena los argumentos internamente (e.g. x + x^2),
    # por lo que comprobamos que existan ambas reglas sin depender del orden.
    reglas_aplicadas = [step.rule_name.lower() for step in root_step.sub_steps]

    assert any("potencia" in regla for regla in reglas_aplicadas)
    assert any("variable" in regla for regla in reglas_aplicadas)
