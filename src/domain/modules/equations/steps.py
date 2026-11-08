import sympy

from src.domain.math_engine import MathEngine as SympyAdapter
from src.domain.steps import EducationalStep, StepCoverage, StepOutcome, StepStatus


class EquationStepGenerator:
    """Motor educativo para la resolución de ecuaciones."""

    def __init__(self, adapter: SympyAdapter):
        self.adapter = adapter

    def generate_steps(
        self, expr: sympy.Expr, var: sympy.Symbol, solutions: object
    ) -> StepOutcome:
        try:
            # Estado inicial matemático
            if isinstance(expr, sympy.Eq):
                before = sympy.latex(expr)
                lhs, rhs = expr.lhs, expr.rhs
            else:
                before = f"{sympy.latex(expr)} = 0"
                lhs, rhs = expr, sympy.Integer(0)

            if solutions == sympy.EmptySet:
                after = "\\text{Sin solución}"
            else:
                after = f"{var.name} \\in {sympy.latex(solutions)}"

            sub_steps = self._breakdown_steps(lhs, rhs, var, solutions)
            coverage = StepCoverage.COMPLETE if sub_steps else StepCoverage.PARTIAL
            root_step = EducationalStep(
                step_id="step_eq_0",
                rule_name="Resolución de Ecuación",
                explanation=(
                    "Se aplica el motor de cálculo algebraico para "
                    "despejar la variable indicada y encontrar sus "
                    "raíces."
                ),
                before_latex=before,
                after_latex=after,
                sub_steps=sub_steps,
            )

            return StepOutcome(
                status=StepStatus.SUCCESS,
                coverage=coverage,
                steps=[root_step],
            )
        except Exception:
            return StepOutcome(
                status=StepStatus.FAILED, coverage=StepCoverage.UNAVAILABLE, steps=[]
            )

    def _roots(
        self, solutions: object, difference: sympy.Expr, variable: sympy.Symbol
    ) -> list[sympy.Expr]:
        if isinstance(solutions, sympy.FiniteSet):
            return list(solutions)
        if isinstance(solutions, (list, tuple)):
            return list(solutions)
        return list(sympy.solve(difference, variable))

    def _breakdown_steps(
        self,
        lhs: sympy.Expr,
        rhs: sympy.Expr,
        variable: sympy.Symbol,
        solutions: object,
    ) -> list[EducationalStep]:
        try:
            difference = sympy.expand(lhs - rhs)
            polynomial = sympy.Poly(difference, variable)
            degree = polynomial.degree()
        except (sympy.PolynomialError, TypeError, ValueError, AttributeError):
            return []
        if degree not in (1, 2):
            return []
        standard = sympy.Eq(difference, 0)
        steps = [
            EducationalStep(
                step_id="step_eq_standard",
                rule_name="Forma estándar",
                explanation=(
                    "Se trasladan todos los términos a un miembro para "
                    "obtener P(x) = 0."
                ),
                before_latex=sympy.latex(sympy.Eq(lhs, rhs)),
                after_latex=sympy.latex(standard),
            )
        ]
        coefficients = polynomial.all_coeffs()
        if degree == 1:
            a, b = coefficients
            root = sympy.simplify(-b / a)
            steps.append(
                EducationalStep(
                    step_id="step_eq_linear_coefficients",
                    rule_name="Coeficientes de la ecuación lineal",
                    explanation=(
                        "La ecuación tiene la forma a·x + b = 0; se "
                        "identifican a y b para despejar la incógnita."
                    ),
                    before_latex=sympy.latex(standard),
                    after_latex=(
                        f"a = {sympy.latex(a)},\\quad b = {sympy.latex(b)}"
                    ),
                )
            )
            steps.append(
                EducationalStep(
                    step_id="step_eq_linear_root",
                    rule_name="Despeje de la incógnita",
                    explanation=(
                        "Se despeja la variable dividiendo entre el "
                        "coeficiente a."
                    ),
                    before_latex=sympy.latex(standard),
                    after_latex=f"{sympy.latex(variable)} = {sympy.latex(root)}",
                )
            )
            return steps
        a, b, c = coefficients
        discriminant = sympy.simplify(b**2 - 4 * a * c)
        steps.append(
            EducationalStep(
                step_id="step_eq_quadratic_discriminant",
                rule_name="Discriminante",
                explanation=(
                    "Se calcula Δ = b² - 4ac para determinar el número "
                    "y la naturaleza de las raíces."
                ),
                before_latex=(
                    f"a = {sympy.latex(a)},\\quad b = {sympy.latex(b)},"
                    f"\\quad c = {sympy.latex(c)}"
                ),
                after_latex=f"\\Delta = {sympy.latex(discriminant)}",
            )
        )
        roots = self._roots(solutions, difference, variable)
        if roots:
            found = ", ".join(sympy.latex(root) for root in roots)
            after_roots = f"{sympy.latex(variable)} \\in \\left\\{{{found}\\right\\}}"
        else:
            after_roots = "\\text{Sin raíces reales}"
        steps.append(
            EducationalStep(
                step_id="step_eq_quadratic_roots",
                rule_name="Fórmula general",
                explanation=(
                    "Se aplica la fórmula general con el discriminante "
                    "obtenido para hallar las raíces."
                ),
                before_latex=f"\\Delta = {sympy.latex(discriminant)}",
                after_latex=after_roots,
            )
        )
        return steps
