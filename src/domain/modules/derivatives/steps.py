from __future__ import annotations

import sympy

from src.domain.math_engine import MathEngine as SympyAdapter
from src.domain.steps import (
    EducationalStep,
    StepCoverage,
    StepOutcome,
    StepStatus,
)


class DerivativeStepGenerator:
    """Genera explicaciones estructurales y declara cobertura parcial."""

    def __init__(self, adapter: SympyAdapter) -> None:
        self.adapter = adapter

    def generate_steps(
        self,
        expr: sympy.Expr,
        var: sympy.Symbol,
        order: int = 1,
    ) -> StepOutcome:
        try:
            current = expr
            steps = []
            complete = True

            for index in range(order):
                step, step_complete = self._explain(
                    current,
                    var,
                    f"derivative_{index + 1}",
                )
                steps.append(step)
                complete = complete and step_complete
                current = self.adapter.diff(current, var)

            return StepOutcome(
                status=StepStatus.SUCCESS,
                coverage=(StepCoverage.COMPLETE if complete else StepCoverage.PARTIAL),
                steps=steps,
            )
        except Exception:
            return StepOutcome(
                status=StepStatus.FAILED,
                coverage=StepCoverage.UNAVAILABLE,
                steps=[],
            )

    def _before(self, expr: sympy.Expr, var: sympy.Symbol) -> str:
        derivative = sympy.Derivative(expr, var, evaluate=False)
        return sympy.latex(derivative)

    def _after(self, expr: sympy.Expr, var: sympy.Symbol) -> str:
        return sympy.latex(self.adapter.diff(expr, var))

    def _step(
        self,
        step_id: str,
        rule_name: str,
        explanation: str,
        expr: sympy.Expr,
        var: sympy.Symbol,
        sub_steps: list[EducationalStep] | None = None,
    ) -> EducationalStep:
        return EducationalStep(
            step_id=step_id,
            rule_name=rule_name,
            explanation=explanation,
            before_latex=self._before(expr, var),
            after_latex=self._after(expr, var),
            sub_steps=sub_steps or [],
        )

    def _explain(
        self,
        expr: sympy.Expr,
        var: sympy.Symbol,
        prefix: str,
    ) -> tuple[EducationalStep, bool]:
        # Constantes numéricas, constantes simbólicas y parámetros.
        if not expr.has(var):
            step = self._step(
                prefix,
                "Derivada de una constante",
                (
                    f"La expresión {sympy.latex(expr)} no depende de "
                    f"{sympy.latex(var)}. Por eso permanece constante "
                    "durante la derivación y su derivada es 0."
                ),
                expr,
                var,
            )
            return step, True

        # Variable objetivo.
        if expr == var:
            step = self._step(
                prefix,
                "Derivada de la variable",
                (
                    f"La expresión es la propia variable "
                    f"{sympy.latex(var)}. Su tasa de cambio respecto de "
                    "sí misma es 1."
                ),
                expr,
                var,
            )
            return step, True

        # Linealidad sobre sumas y restas.
        if expr.is_Add:
            children: list[EducationalStep] = []
            complete = True
            for index, term in enumerate(expr.args):
                child, child_complete = self._explain(
                    term,
                    var,
                    f"{prefix}_{index}",
                )
                children.append(child)
                complete = complete and child_complete

            step = self._step(
                prefix,
                "Regla de la suma",
                (
                    "La derivada es lineal: se deriva cada término por "
                    "separado y después se reúnen los resultados. Los "
                    "signos negativos permanecen asociados a su término."
                ),
                expr,
                var,
                children,
            )
            return step, complete

        # Potencias. Se evalúan antes del cociente porque 1/x aparece
        # internamente como x**(-1).
        if expr.is_Pow:
            base, exponent = expr.as_base_exp()

            if not exponent.has(var):
                child, child_complete = self._explain(
                    base,
                    var,
                    f"{prefix}_base",
                )
                step = self._step(
                    prefix,
                    "Regla de la potencia",
                    (
                        "El exponente es constante. Para una función "
                        "u(x), d(u^n)/dx = n·u^(n-1)·u'. Primero se "
                        f"reduce el exponente {sympy.latex(exponent)} en "
                        "una unidad y después se multiplica por la "
                        "derivada de la base."
                    ),
                    expr,
                    var,
                    [child],
                )
                return step, child_complete

            base_step, base_complete = self._explain(
                base,
                var,
                f"{prefix}_base",
            )
            exponent_step, exponent_complete = self._explain(
                exponent,
                var,
                f"{prefix}_exponent",
            )
            step = self._step(
                prefix,
                "Potencia con exponente variable",
                (
                    "La base y el exponente dependen de la variable. Se "
                    "usa diferenciación logarítmica: para y=u^v, "
                    "y'=u^v·(v'·ln(u)+v·u'/u). En el dominio real se "
                    "deben respetar las condiciones necesarias para "
                    "utilizar ln(u)."
                ),
                expr,
                var,
                [base_step, exponent_step],
            )
            return step, base_complete and exponent_complete

        # Cociente. SymPy representa divisiones mediante potencias
        # negativas, por lo que se recuperan numerador y denominador.
        numerator, denominator = expr.as_numer_denom()
        if denominator != 1 and denominator.has(var):
            numerator_step, numerator_complete = self._explain(
                numerator,
                var,
                f"{prefix}_numerator",
            )
            denominator_step, denominator_complete = self._explain(
                denominator,
                var,
                f"{prefix}_denominator",
            )
            step = self._step(
                prefix,
                "Regla del cociente",
                (
                    f"Se identifica u = {sympy.latex(numerator)} como el numerador "
                    f"y v = {sympy.latex(denominator)} como el denominador. "
                    "Se aplica la regla del cociente (u/v)' = (u'·v - u·v') / v²."
                ),
                expr,
                var,
                [numerator_step, denominator_step],
            )
            return step, numerator_complete and denominator_complete

        # Productos y múltiplos constantes.
        if expr.is_Mul:
            independent, dependent = expr.as_independent(
                var,
                as_Add=False,
            )
            if independent != 1 and dependent != 1:
                child, child_complete = self._explain(
                    dependent,
                    var,
                    f"{prefix}_dependent",
                )
                step = self._step(
                    prefix,
                    "Regla del múltiplo constante",
                    (
                        f"El factor {sympy.latex(independent)} no depende "
                        f"de {sympy.latex(var)} y puede mantenerse fuera "
                        "de la derivación. Solo se deriva el factor que "
                        "sí depende de la variable."
                    ),
                    expr,
                    var,
                    [child],
                )
                return step, child_complete

            factors = list(expr.args)
            children = []
            complete = True
            for index, factor in enumerate(factors):
                child, child_complete = self._explain(
                    factor,
                    var,
                    f"{prefix}_factor_{index}",
                )
                children.append(child)
                complete = complete and child_complete

            if len(factors) == 2:
                u, v = factors
                explanation = (
                    f"Se aplica la regla del producto (u·v)' = u'·v + u·v' "
                    f"con u = {sympy.latex(u)} y v = {sympy.latex(v)}."
                )
            else:
                explanation = (
                    "Todos los factores dependen de la variable. Para "
                    "múltiples factores se suma un término por cada factor "
                    "derivado, conservando sin derivar los demás."
                )

            step = self._step(
                prefix,
                "Regla del producto",
                explanation,
                expr,
                var,
                children,
            )
            return step, complete

        # Funciones elementales y regla de la cadena.
        function_rules: dict[object, tuple[str, str]] = {
            sympy.sin: (
                "Derivada del seno",
                "La derivada de sin(u) es cos(u)·u'.",
            ),
            sympy.cos: (
                "Derivada del coseno",
                "La derivada de cos(u) es -sin(u)·u'.",
            ),
            sympy.tan: (
                "Derivada de la tangente",
                "La derivada de tan(u) es sec²(u)·u'.",
            ),
            sympy.exp: (
                "Derivada de la exponencial",
                "La derivada de exp(u) es exp(u)·u'.",
            ),
            sympy.log: (
                "Derivada del logaritmo natural",
                (
                    "La derivada de ln(u) es u'/u, respetando las "
                    "condiciones de dominio de la expresión."
                ),
            ),
            sympy.Abs: (
                "Derivada del valor absoluto",
                (
                    "Donde la función es derivable, la derivada de "
                    "|u| es sign(u)·u'. En los puntos donde u=0 se "
                    "debe revisar la derivabilidad."
                ),
            ),
            sympy.asin: (
                "Derivada del arcoseno",
                "La derivada de asin(u) es u'/sqrt(1-u²).",
            ),
            sympy.acos: (
                "Derivada del arcocoseno",
                "La derivada de acos(u) es -u'/sqrt(1-u²).",
            ),
            sympy.atan: (
                "Derivada del arcotangente",
                "La derivada de atan(u) es u'/(1+u²).",
            ),
        }

        if expr.func in function_rules and len(expr.args) == 1:
            argument = expr.args[0]
            child, child_complete = self._explain(
                argument,
                var,
                f"{prefix}_inner",
            )
            title, formula = function_rules[expr.func]
            step = self._step(
                prefix,
                title,
                (
                    f"{formula} Aquí, la función exterior es evaluada en u, "
                    f"siendo la función interior u = {sympy.latex(argument)}, "
                    "por lo que se aplica la regla de la cadena multiplicando por u'."
                ),
                expr,
                var,
                [child],
            )
            return step, child_complete

        # Fallback honesto.
        step = self._step(
            prefix,
            "Derivación no desarrollada paso a paso",
            (
                "El motor de cálculo obtuvo una derivada, pero el motor "
                "educativo todavía no dispone de una regla detallada "
                f"para la estructura {expr.func}. El resultado puede "
                "mostrarse, pero el procedimiento debe marcarse como "
                "parcial."
            ),
            expr,
            var,
        )
        return step, False
