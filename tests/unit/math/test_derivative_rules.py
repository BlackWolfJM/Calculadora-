import sympy

from src.domain.modules.derivatives.steps import DerivativeStepGenerator
from src.domain.steps import StepCoverage
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def build_generator():
    adapter = SympyAdapter()
    return MathParser(), adapter, DerivativeStepGenerator(adapter)


def generate(text: str, variable: str = "x"):
    parser, adapter, generator = build_generator()
    ast = parser.parse(text)
    expr = adapter.ast_to_sympy(ast)
    var = sympy.Symbol(variable, real=True)
    return generator.generate_steps(expr, var)


def test_constant_rule():
    outcome = generate("7")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "constante" in outcome.steps[0].rule_name.lower()
    assert outcome.steps[0].after_latex == "0"


def test_target_variable_rule():
    outcome = generate("x")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "variable" in outcome.steps[0].rule_name.lower()
    assert outcome.steps[0].after_latex == "1"


def test_independent_symbol_is_constant():
    outcome = generate("y", variable="x")
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "constante" in outcome.steps[0].rule_name.lower()
    assert outcome.steps[0].after_latex == "0"


def test_sum_has_substeps():
    outcome = generate("x^3 + 4*x")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "suma" in root.rule_name.lower()
    assert len(root.sub_steps) == 2


def test_product_has_factor_substeps():
    outcome = generate("x^2*sin(x)")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "producto" in root.rule_name.lower()
    assert len(root.sub_steps) == 2


def test_constant_multiple_is_not_general_product():
    outcome = generate("3*x^2")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "múltiplo constante" in root.rule_name.lower()
    assert len(root.sub_steps) == 1


def test_quotient_rule():
    outcome = generate("sin(x)/x")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "cociente" in root.rule_name.lower()
    assert len(root.sub_steps) == 2


def test_chain_rule_inside_sine():
    outcome = generate("sin(x^2)")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "seno" in root.rule_name.lower()
    assert len(root.sub_steps) == 1


def test_variable_exponent():
    outcome = generate("x^x")
    root = outcome.steps[0]
    assert outcome.coverage == StepCoverage.COMPLETE
    assert "exponente variable" in root.rule_name.lower()
    assert len(root.sub_steps) == 2
