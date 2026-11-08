from src.domain.modules.equations.module import EquationsModule
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def test_equation_solving():
    parser = MathParser()
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    # x^2 = 4 -> x = 2, x = -2
    ast = parser.parse("x^2 = 4")
    response = module.solve(ast, {"variable": "x"})

    assert response.status.value == "success"
    text_res = response.calculation.primary_result.value.canonical_text
    assert "x = -2" in text_res or "x = 2" in text_res

    # 3*x = 2*x + 5 -> x = 5
    ast2 = parser.parse("3*x = 2*x + 5")
    response2 = module.solve(ast2, {"variable": "x"})
    assert response2.status.value == "success"
    assert "x = 5" in response2.calculation.primary_result.value.canonical_text


def test_equation_identity():
    # x = x -> Todos los reales
    parser = MathParser()
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    ast = parser.parse("x = x")
    response = module.solve(ast, {"variable": "x"})

    assert response.status.value == "success"
    text = response.calculation.primary_result.value.canonical_text
    assert "Todos los números reales son solución" in text or "Reals" in text


def test_equation_no_solution():
    # x = x + 1 -> Sin solución
    parser = MathParser()
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    ast = parser.parse("x = x + 1")
    response = module.solve(ast, {"variable": "x"})

    assert response.status.value == "success"
    text = response.calculation.primary_result.value.canonical_text
    assert "No existe solución real" in text or "EmptySet" in text

    # x^2 + 1 = 0 -> Sin solución real
    ast2 = parser.parse("x^2 + 1 = 0")
    response2 = module.solve(ast2, {"variable": "x"})
    assert response2.status.value == "success"
    text2 = response2.calculation.primary_result.value.canonical_text
    assert "No existe solución real" in text2 or "EmptySet" in text2


def test_equation_error_handling():
    # Simular un error en el adaptador para ver si devuelve FAILED
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    # Un AST corrupto para provocar fallo
    response = module.solve(None, {"variable": "x"})
    from src.domain.responses import ResolutionStatus

    assert response.status == ResolutionStatus.FAILED


def test_equation_linear_steps_are_complete_and_ordered():
    parser = MathParser()
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    response = module.solve(parser.parse("3*x = 2*x + 5"), {"variable": "x"})
    procedure = response.procedure

    assert procedure is not None
    assert procedure.coverage.value == "complete"
    step = procedure.steps[0]
    assert [item.rule_name for item in step.sub_steps] == [
        "Forma estándar",
        "Coeficientes de la ecuación lineal",
        "Despeje de la incógnita",
    ]
    assert "x = 5" in step.sub_steps[-1].after_latex


def test_equation_quadratic_steps_include_discriminant_and_roots():
    parser = MathParser()
    adapter = SympyAdapter()
    module = EquationsModule(adapter)

    response = module.solve(parser.parse("x^2 = 4"), {"variable": "x"})
    procedure = response.procedure

    assert procedure is not None
    assert procedure.coverage.value == "complete"
    step = procedure.steps[0]
    rules = [item.rule_name for item in step.sub_steps]
    assert "Forma estándar" in rules
    assert "Discriminante" in rules
    assert "Fórmula general" in rules
    assert any("Delta" in item.after_latex for item in step.sub_steps)

