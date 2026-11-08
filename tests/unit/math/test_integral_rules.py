import pytest
import sympy

from src.domain.modules.integrals.module import IntegralsModule
from src.domain.modules.integrals.steps import IntegralStepGenerator
from src.domain.modules.integrals.substitution import (
    analyze_substitution,
    format_math_latex,
)
from src.domain.steps import StepCoverage, StepStatus
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def build_generator():
    adapter = SympyAdapter()
    return MathParser(), adapter, IntegralStepGenerator(adapter)


def generate(text: str, variable: str = "x"):
    parser, adapter, generator = build_generator()
    ast = parser.parse(text)
    expr = adapter.ast_to_sympy(ast)
    var = sympy.Symbol(variable, real=True)
    return generator.generate_steps(expr, var)


def test_integral_of_constant():
    outcome = generate("5")
    assert outcome.status == StepStatus.SUCCESS
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "constante" in outcome.steps[0].rule_name.lower()
    assert len(outcome.steps) == 2


def test_integral_of_variable():
    outcome = generate("x")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "variable" in outcome.steps[0].rule_name.lower()


def test_integral_power_rule():
    outcome = generate("x^3")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "potencia" in outcome.steps[0].rule_name.lower()


def test_integral_reciprocal_rule():
    outcome = generate("1/x")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "recíproco" in outcome.steps[0].rule_name.lower()


def test_integral_sum_has_substeps():
    outcome = generate("x^2 + 3*x")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "linealidad" in root.rule_name.lower()
    assert len(root.sub_steps) == 2


def test_integral_constant_multiple():
    outcome = generate("3*x^2")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "múltiplo constante" in root.rule_name.lower()
    assert len(root.sub_steps) == 1


def test_integral_sine_linear_argument():
    outcome = generate("sin(2*x)")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "seno lineal" in root.rule_name.lower()


def test_only_one_integration_constant_step():
    outcome = generate("x^2 + x")
    constant_steps = [
        step
        for step in outcome.steps
        if "constante de integración" in step.rule_name.lower()
    ]
    assert len(constant_steps) == 1


@pytest.mark.parametrize(
    "case_id,expr_str,expected_method,expected_u,expected_k,expected_antideriv,points",
    [
        (
            "T01",
            "3*x^2*cos(x^3+2)",
            "SUB_EXACT",
            "x**3 + 2",
            "1",
            "sin(x**3 + 2)",
            (-2, 0, 2),
        ),
        (
            "T02",
            "5*x*(x^2+4)^3",
            "SUB_CONSTANT_FACTOR",
            "x**2 + 4",
            "5/2",
            "5*(x**2 + 4)**4/8",
            (-2, 0, 2),
        ),
        (
            "T03",
            "x*sqrt(x+1)",
            "SUB_INVERSE_AFFINE",
            "x + 1",
            "1",
            "2*(x + 1)**(5/2)/5 - 2*(x + 1)**(3/2)/3",
            (0, 1, 3),
        ),
        (
            "T04",
            "x*exp(x^2)*cos(exp(x^2))",
            "SUB_NESTED",
            "exp(x**2)",
            "1/2",
            "sin(exp(x**2))/2",
            (-1, 0, 1),
        ),
        (
            "T05",
            "x/(x^2-1)",
            "SUB_LOG_ABSOLUTE",
            "x**2 - 1",
            "1/2",
            "log(Abs(x**2 - 1))/2",
            (-2, -sympy.Rational(1, 2), 0, sympy.Rational(1, 2), 2),
        ),
        (
            "T07",
            "x/sqrt(x^2+2*x+5)",
            "SUB_COMPLETE_SQUARE",
            "x + 1",
            "1",
            "sqrt(x**2 + 2*x + 5) - asinh((x + 1)/2)",
            (-2, 0, 2),
        ),
    ],
)
def test_substitution_specification_cases_t01_to_t07(
    case_id,
    expr_str,
    expected_method,
    expected_u,
    expected_k,
    expected_antideriv,
    points,
):
    parser, adapter, generator = build_generator()
    ast = parser.parse(expr_str)
    expr = adapter.ast_to_sympy(ast)
    var = sympy.Symbol("x", real=True)

    analysis = analyze_substitution(expr, var)
    assert analysis is not None, case_id
    assert analysis.status == "verified"
    assert analysis.method_id == expected_method
    expected_u_sym = sympy.sympify(expected_u, locals={"x": var})
    expected_k_sym = sympy.sympify(expected_k, locals={"x": var})
    assert sympy.simplify(analysis.u_expr - expected_u_sym) == 0
    assert sympy.simplify(analysis.const_factor - expected_k_sym) == 0
    assert len(analysis.steps) == 9
    assert analysis.proof_residual == 0

    expected_sym = sympy.sympify(expected_antideriv, locals={"x": var})
    residual = sympy.diff(expected_sym, var) - expr
    global_res = sympy.simplify(residual)
    if global_res != 0:
        assert all(sympy.simplify(residual.subs(var, pt)) == 0 for pt in points)

    outcome = generator.generate_steps(expr, var)
    assert outcome.status == StepStatus.SUCCESS
    assert outcome.coverage == StepCoverage.COMPLETE
    assert len(outcome.steps) == 9
    for step in outcome.steps:
        assert r"\(" in step.explanation and r"\)" in step.explanation
        assert not step.before_latex.startswith(r"\(")
        assert not step.after_latex.startswith(r"\(")


def test_substitution_t05_log_abs_and_t07_arsinh_latex_formatting():
    parser, adapter, _ = build_generator()
    module = IntegralsModule(adapter)

    res_t05 = module.solve(parser.parse("x/(x^2-1)"), {"variable": "x"})
    assert "Abs(x**2 - 1)" in res_t05.calculation.primary_result.value.canonical_text
    assert r"\ln\left|" in res_t05.calculation.primary_result.value.latex

    res_t07 = module.solve(parser.parse("x/sqrt(x^2+2*x+5)"), {"variable": "x"})
    assert r"\operatorname{arsinh}" in res_t07.calculation.primary_result.value.latex


def test_substitution_t06_definite_integral_bounds_transformation():
    x = sympy.Symbol("x", real=True)
    definite_integral = sympy.Integral(2 * x * sympy.exp(x**2), (x, 0, 1))
    analysis = analyze_substitution(definite_integral)
    assert analysis is not None
    assert analysis.status == "verified"
    assert analysis.method_id == "SUB_DEFINITE_BOUNDS"
    assert analysis.new_bounds == (0, 1)
    assert sympy.simplify(analysis.definite_value - (sympy.E - 1)) == 0
    assert len(analysis.steps) == 9
    assert "+ C" not in analysis.steps[7].after_latex


def test_substitution_t08_rejected_honest_diagnostic():
    outcome = generate("exp(x^2)")
    assert outcome.coverage == StepCoverage.PARTIAL
    assert len(outcome.steps) == 5
    assert "Rechazar ruta" in outcome.steps[3].rule_name
    assert "erfi" in outcome.steps[4].after_latex
    assert format_math_latex(sympy.Symbol("x")) == "x"
