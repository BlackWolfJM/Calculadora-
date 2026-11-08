from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from src.domain.steps import EducationalStep


@dataclass(frozen=True)
class SubstitutionAnalysis:
    """Resultado estructurado y verificable del análisis de sustitución."""

    method_id: str
    u_expr: sp.Expr
    du_dx: sp.Expr
    const_factor: sp.Expr
    integrand_in_u: sp.Expr
    antideriv_in_u: sp.Expr
    antideriv_in_x: sp.Expr
    proof_residual: sp.Expr
    status: str  # "verified", "conditional", "unsupported", "rejected"
    domain_latex: str = r"x \in \mathbb{R}"
    x_of_u: sp.Expr | None = None
    dx_du: sp.Expr | None = None
    completed_quadratic: sp.Expr | None = None
    original_quadratic: sp.Expr | None = None
    original_bounds: tuple[sp.Expr, sp.Expr] | None = None
    new_bounds: tuple[sp.Expr, sp.Expr] | None = None
    definite_value: sp.Expr | None = None
    assumptions: tuple[str, ...] = ()
    steps: tuple[EducationalStep, ...] = field(default_factory=tuple)


def format_math_latex(expr: sp.Expr) -> str:
    """Convierte una expresión SymPy a LaTeX compatible con KaTeX."""
    raw = sp.latex(expr)
    raw = raw.replace(r"\operatorname{asinh}", r"\operatorname{arsinh}")
    raw = raw.replace(r"\operatorname{acosh}", r"\operatorname{arcosh}")
    raw = raw.replace(r"\operatorname{atanh}", r"\operatorname{artanh}")
    for node in sp.preorder_traversal(expr):
        if node.func == sp.log and len(node.args) == 1:
            arg = node.args[0]
            if arg.func == sp.Abs and len(arg.args) == 1:
                inner_ltx = sp.latex(arg.args[0])
                target = sp.latex(node)
                raw = raw.replace(target, rf"\ln\left|{inner_ltx}\right|")
    return raw


def _is_direct_elementary_in_var(expr: sp.Expr, var: sp.Symbol) -> bool:
    """Indica si expr se resuelve por regla directa elemental sin sustitución."""
    if not expr.has(var) or expr == var:
        return True
    if expr.is_Pow:
        base, exp = expr.as_base_exp()
        deriv = sp.diff(base, var)
        is_linear_base = deriv != 0 and not deriv.has(var)
        if not exp.has(var) and (base == var or is_linear_base):
            return True
        if not base.has(var) and exp.has(var):
            exp_deriv = sp.diff(exp, var)
            if exp_deriv != 0 and not exp_deriv.has(var):
                return True
    if len(expr.args) == 1 and expr.func in (sp.sin, sp.cos, sp.exp, sp.tan):
        arg_deriv = sp.diff(expr.args[0], var)
        if arg_deriv != 0 and not arg_deriv.has(var):
            return True
    if expr.func == sp.log and expr.args == (var,):
        return True
    if expr.is_Mul:
        indep, dep = expr.as_independent(var, as_Add=False)
        if indep != 1 and dep != 1 and _is_direct_elementary_in_var(dep, var):
            return True
    if expr.is_Add:
        return all(_is_direct_elementary_in_var(term, var) for term in expr.args)
    return False


def candidate_subexpressions(expr: sp.Expr, var: sp.Symbol) -> list[sp.Expr]:
    """Extrae candidatos interiores g(x) del AST ordenados por utilidad."""
    seen: list[sp.Expr] = []

    def _add(cand: sp.Expr) -> None:
        if cand.has(var) and cand != var and cand != expr and cand not in seen:
            seen.append(cand)

    for node in sp.preorder_traversal(expr):
        if node.is_Function and node.args:
            _add(node.args[0])
        elif isinstance(node, sp.Pow):
            _add(node.base)
            if node.exp.has(var):
                _add(node.exp)

    _, den = sp.fraction(sp.together(expr))
    if den.has(var) and den != 1:
        _add(den)
        if isinstance(den, sp.Pow):
            _add(den.base)

    return seen


def _has_nested_composition(g: sp.Expr, var: sp.Symbol) -> bool:
    """Detecta si g(x) contiene a su vez una composición no trivial."""
    for node in sp.preorder_traversal(g):
        if node.is_Function and node.args:
            arg = node.args[0]
            if arg != var and arg.has(var):
                return True
        if isinstance(node, sp.Pow) and node.exp.has(var) and node.exp != var:
            return True
    return False


def _integrate_in_u_safely(h_u: sp.Expr, u: sp.Symbol) -> tuple[sp.Expr | None, bool]:
    """Integra h_u respecto de u usando log(Abs(u)) para k/u."""
    u_prod = sp.simplify(h_u * u)
    if not u_prod.has(u) and u_prod != 0:
        return u_prod * sp.log(sp.Abs(u)), True

    antideriv = sp.integrate(h_u, u)
    if antideriv.has(sp.Integral):
        return None, False
    return antideriv, False


def _verify_derivative_identity(
    antideriv_x: sp.Expr, expr: sp.Expr, var: sp.Symbol
) -> sp.Expr:
    """Comprueba que d/dx(antideriv_x) - expr sea 0 en el dominio real."""
    cleaned = antideriv_x.replace(lambda n: n.func == sp.Abs, lambda n: n.args[0])
    residual = sp.simplify(sp.diff(cleaned, var) - expr)
    if residual != 0:
        residual = sp.simplify(sp.together(sp.diff(cleaned, var) - expr))
    return residual


def _build_standard_9_steps(
    *,
    tag: str,
    method_id: str,
    expr: sp.Expr,
    var: sp.Symbol,
    u_sym: sp.Symbol,
    u_expr: sp.Expr,
    du_dx: sp.Expr,
    const_factor: sp.Expr,
    integrand_in_u: sp.Expr,
    antideriv_in_u: sp.Expr,
    antideriv_in_x: sp.Expr,
    domain_latex: str,
    x_of_u: sp.Expr | None = None,
    dx_du: sp.Expr | None = None,
    unexpanded_in_u: sp.Expr | None = None,
    completed_quadratic: sp.Expr | None = None,
    original_quadratic: sp.Expr | None = None,
    bounds: tuple[sp.Expr, sp.Expr] | None = None,
    new_bounds: tuple[sp.Expr, sp.Expr] | None = None,
    definite_value: sp.Expr | None = None,
    is_log_abs: bool = False,
) -> tuple[EducationalStep, ...]:
    """Construye los 9 pasos EducationalStep de la especificación."""
    var_ltx = format_math_latex(var)
    expr_ltx = format_math_latex(expr)
    u_ltx = format_math_latex(u_expr)
    du_dx_ltx = format_math_latex(du_dx)
    k_ltx = format_math_latex(const_factor)
    h_u_ltx = format_math_latex(integrand_in_u)
    anti_u_ltx = format_math_latex(antideriv_in_u)
    anti_x_ltx = format_math_latex(antideriv_in_x)

    if bounds is not None:
        a_ltx = format_math_latex(bounds[0])
        b_ltx = format_math_latex(bounds[1])
        int_prefix = rf"\int_{{{a_ltx}}}^{{{b_ltx}}}"
    else:
        int_prefix = r"\int"

    # Paso 1
    if (
        method_id == "SUB_COMPLETE_SQUARE"
        and original_quadratic is not None
        and completed_quadratic is not None
    ):
        orig_q_ltx = format_math_latex(original_quadratic)
        comp_q_ltx = format_math_latex(completed_quadratic)
        rewritten = expr.subs(original_quadratic, completed_quadratic)
        rew_ltx = format_math_latex(rewritten)
        step_1 = EducationalStep(
            step_id=f"SUB_01_{tag}",
            rule_name="Reconocimiento del patrón y completación de cuadrado",
            explanation=(
                f"Completamos el cuadrado en el trinomio cuadrático: "
                f"\\({orig_q_ltx} = {comp_q_ltx}\\). Transformación: "
                f"\\({int_prefix} {expr_ltx}\\,d{var_ltx}\\) pasa a "
                f"\\({int_prefix} {rew_ltx}\\,d{var_ltx}\\)."
            ),
            before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
            after_latex=rf"{int_prefix} {rew_ltx}\,d{var_ltx}",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_01_1_{tag}",
                    rule_name="Completar cuadrado",
                    explanation=(
                        f"La identidad \\({orig_q_ltx} = {comp_q_ltx}\\) "
                        "se verifica expandiendo el binomio."
                    ),
                    before_latex=orig_q_ltx,
                    after_latex=comp_q_ltx,
                ),
                EducationalStep(
                    step_id=f"SUB_01_2_{tag}",
                    rule_name="Registrar restricciones de dominio",
                    explanation=(
                        f"Conservamos las condiciones \\({domain_latex}\\) "
                        "antes de transformar el integrando."
                    ),
                    before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
                    after_latex=(
                        rf"{int_prefix} {rew_ltx}\,d{var_ltx}\quad({domain_latex})"
                    ),
                ),
            ],
        )
    else:
        step_1 = EducationalStep(
            step_id=f"SUB_01_{tag}",
            rule_name="Reconocimiento del patrón",
            explanation=(
                f"Buscamos una función interior \\(u = {u_ltx}\\) dentro "
                f"de \\({expr_ltx}\\), cuya derivada se relacione con los "
                "factores restantes."
            ),
            before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
            after_latex=(
                rf"{int_prefix} \underbrace{{{expr_ltx}}}"
                rf"_{{\text{{composición}}}}\,d{var_ltx}"
            ),
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_01_1_{tag}",
                    rule_name="Localizar argumentos y bases candidatas",
                    explanation=(
                        f"Identificamos el subárbol \\({u_ltx}\\) como "
                        "expresión interior candidata."
                    ),
                    before_latex=expr_ltx,
                    after_latex=f"u = {u_ltx}",
                ),
                EducationalStep(
                    step_id=f"SUB_01_2_{tag}",
                    rule_name="Registrar restricciones de dominio",
                    explanation=(
                        f"Conservamos las condiciones \\({domain_latex}\\) "
                        "antes de transformar el integrando."
                    ),
                    before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
                    after_latex=(
                        rf"{int_prefix} {expr_ltx}\,d{var_ltx}\quad({domain_latex})"
                    ),
                ),
            ],
        )

    # Paso 2
    step_2 = EducationalStep(
        step_id=f"SUB_02_{tag}",
        rule_name="Elección de la sustitución",
        explanation=(
            f"Elegimos \\(u = {u_ltx}\\) para reemplazar la parte compuesta; "
            "esta igualdad define el cambio de variable propuesto."
        ),
        before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
        after_latex=f"u = {u_ltx}",
        sub_steps=[
            EducationalStep(
                step_id=f"SUB_02_1_{tag}",
                rule_name="Registrar mapeo simbólico",
                explanation=(
                    f"La sustitución \\(u = {u_ltx}\\) se vincula al "
                    f"subárbol correspondiente de \\({expr_ltx}\\)."
                ),
                before_latex=expr_ltx,
                after_latex=rf"{u_ltx} \mapsto u",
            )
        ],
    )

    # Paso 3
    du_rhs = f"d{var_ltx}" if du_dx == 1 else rf"{du_dx_ltx}\,d{var_ltx}"
    step_3 = EducationalStep(
        step_id=f"SUB_03_{tag}",
        rule_name="Derivación y diferencial",
        explanation=(
            f"Derivamos \\(u = {u_ltx}\\) respecto de \\({var_ltx}\\): "
            f"\\(\\frac{{du}}{{d{var_ltx}}} = {du_dx_ltx}\\), por lo que "
            f"\\(du = {du_rhs}\\)."
        ),
        before_latex=f"u = {u_ltx}",
        after_latex=f"du = {du_rhs}",
        sub_steps=[
            EducationalStep(
                step_id=f"SUB_03_1_{tag}",
                rule_name="Derivar la expresión interior",
                explanation=(
                    f"Calculamos \\(\\frac{{d}}{{d{var_ltx}}}({u_ltx}) = "
                    f"{du_dx_ltx}\\) aplicando las reglas de derivación."
                ),
                before_latex=rf"\frac{{d}}{{d{var_ltx}}}\left({u_ltx}\right)",
                after_latex=du_dx_ltx,
            ),
            EducationalStep(
                step_id=f"SUB_03_2_{tag}",
                rule_name="Escribir el diferencial",
                explanation=(
                    f"El factor diferencial correspondiente es \\(du = {du_rhs}\\)."
                ),
                before_latex=rf"\frac{{du}}{{d{var_ltx}}} = {du_dx_ltx}",
                after_latex=f"du = {du_rhs}",
            ),
        ],
    )

    # Paso 4
    if x_of_u is not None and dx_du is not None:
        x_u_ltx = format_math_latex(x_of_u)
        dx_du_ltx = "du" if dx_du == 1 else rf"{format_math_latex(dx_du)}\,du"
        step_4 = EducationalStep(
            step_id=f"SUB_04_{tag}",
            rule_name="Despeje y ajuste",
            explanation=(
                f"Despejamos \\({var_ltx} = {x_u_ltx}\\) a partir de "
                f"\\(u = {u_ltx}\\) y usamos \\(d{var_ltx} = {dx_du_ltx}\\) "
                f"para eliminar toda dependencia en \\({var_ltx}\\)."
            ),
            before_latex=f"u = {u_ltx}",
            after_latex=rf"{var_ltx} = {x_u_ltx},\qquad d{var_ltx} = {dx_du_ltx}",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_04_1_{tag}",
                    rule_name="Sustituir también la variable exterior",
                    explanation=(
                        f"Reemplazamos \\({var_ltx} = {x_u_ltx}\\) y "
                        f"\\(d{var_ltx} = {dx_du_ltx}\\)."
                    ),
                    before_latex=f"{var_ltx} = {x_u_ltx}",
                    after_latex=rf"{h_u_ltx}\,du",
                )
            ],
        )
    elif const_factor == 1:
        step_4 = EducationalStep(
            step_id=f"SUB_04_{tag}",
            rule_name="Despeje y ajuste",
            explanation=(
                f"Comparamos el factor diferencial presente con \\(du = {du_rhs}\\). "
                "El diferencial coincide exactamente con ajuste \\(k = 1\\)."
            ),
            before_latex=du_rhs,
            after_latex="du",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_04_1_{tag}",
                    rule_name="Calcular el ajuste",
                    explanation=(
                        "El factor de ajuste entre diferenciales es \\(k = 1\\)."
                    ),
                    before_latex=du_rhs,
                    after_latex=r"1\cdot du",
                )
            ],
        )
    else:
        matched_factor = sp.simplify(const_factor * du_dx)
        matched_ltx = format_math_latex(matched_factor)
        inner_u = sp.simplify(integrand_in_u / const_factor)
        inner_u_ltx = format_math_latex(inner_u)
        step_4 = EducationalStep(
            step_id=f"SUB_04_{tag}",
            rule_name="Despeje y ajuste",
            explanation=(
                f"Como \\(du = {du_rhs}\\), ajustamos el factor constante "
                f"con \\(k = {k_ltx}\\): \\({matched_ltx}\\,d{var_ltx} = "
                f"{k_ltx}\\,du\\)."
            ),
            before_latex=rf"{matched_ltx}\,d{var_ltx}",
            after_latex=rf"{k_ltx}\,du",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_04_1_{tag}",
                    rule_name="Calcular el ajuste constante",
                    explanation=(
                        f"El factor \\(k = {k_ltx}\\) es independiente de "
                        f"\\({var_ltx}\\) y compensa a \\(du = {du_rhs}\\)."
                    ),
                    before_latex=expr_ltx,
                    after_latex=(
                        rf"{k_ltx}\cdot\left({inner_u_ltx}\right)"
                        rf"\big|_{{u={u_ltx}}}\cdot {du_dx_ltx}"
                    ),
                )
            ],
        )

    # Paso 5
    if bounds is not None:
        a_ltx = format_math_latex(bounds[0])
        b_ltx = format_math_latex(bounds[1])
        after_step5 = rf"\int_{{u({a_ltx})}}^{{u({b_ltx})}} {h_u_ltx}\,du"
    elif unexpanded_in_u is not None and unexpanded_in_u != integrand_in_u:
        unexp_ltx = format_math_latex(unexpanded_in_u)
        after_step5 = rf"\int {unexp_ltx}\,du = \int \left({h_u_ltx}\right)\,du"
    elif const_factor != 1 and x_of_u is None:
        inner_u_ltx = format_math_latex(sp.simplify(integrand_in_u / const_factor))
        after_step5 = rf"{k_ltx}\int {inner_u_ltx}\,du"
    else:
        after_step5 = rf"\int {h_u_ltx}\,du"

    step5_substeps = [
        EducationalStep(
            step_id=f"SUB_05_1_{tag}",
            rule_name="Comprobar identidad de cambio",
            explanation=(
                f"Al evaluar \\(u = {u_ltx}\\) en \\({h_u_ltx}\\) y "
                f"multiplicar por \\({du_dx_ltx}\\), se recupera \\({expr_ltx}\\)."
            ),
            before_latex=rf"\left({h_u_ltx}\right)\big|_{{u={u_ltx}}}\cdot {du_dx_ltx}",
            after_latex=expr_ltx,
        )
    ]
    if unexpanded_in_u is not None and unexpanded_in_u != integrand_in_u:
        unexp_ltx = format_math_latex(unexpanded_in_u)
        step5_substeps.insert(
            0,
            EducationalStep(
                step_id=f"SUB_05_0_{tag}",
                rule_name="Distribución algebraica en u",
                explanation=(
                    f"Desarrollamos \\({unexp_ltx} = {h_u_ltx}\\) "
                    "para integrar término a término."
                ),
                before_latex=unexp_ltx,
                after_latex=h_u_ltx,
            ),
        )

    step_5 = EducationalStep(
        step_id=f"SUB_05_{tag}",
        rule_name="Reescritura integral",
        explanation=(
            "Sustituimos la expresión interior y el diferencial para obtener "
            f"una integral únicamente en \\(u\\): \\({after_step5}\\)."
        ),
        before_latex=rf"{int_prefix} {expr_ltx}\,d{var_ltx}",
        after_latex=after_step5,
        sub_steps=step5_substeps,
    )

    # Paso 6
    step6_substeps: list[EducationalStep] = []
    if is_log_abs:
        step6_substeps.append(
            EducationalStep(
                step_id=f"SUB_06_1_{tag}",
                rule_name="Registro del dominio logarítmico",
                explanation=(
                    "Como \\(u \\neq 0\\), la primitiva real de \\(1/u\\) "
                    "es \\(\\ln|u|\\)."
                ),
                before_latex=r"u \neq 0",
                after_latex=r"\ln\left|u\right|",
            )
        )
    elif method_id == "SUB_COMPLETE_SQUARE":
        step6_substeps.extend(
            [
                EducationalStep(
                    step_id=f"SUB_06_1_{tag}",
                    rule_name="Separar y resolver por linealidad",
                    explanation=(
                        "Separamos la fracción mediante linealidad y usamos "
                        "el cambio cuadrático \\(w = u^2 + a^2\\) junto con "
                        "\\(\\operatorname{arsinh}\\)."
                    ),
                    before_latex=rf"\int {h_u_ltx}\,du",
                    after_latex=anti_u_ltx,
                ),
                EducationalStep(
                    step_id=f"SUB_06_2_{tag}",
                    rule_name="Comprobar derivada respecto de u",
                    explanation=(
                        f"Verificamos que \\(\\frac{{d}}{{du}}"
                        f"\\left({anti_u_ltx}\\right) = {h_u_ltx}\\)."
                    ),
                    before_latex=rf"\frac{{d}}{{du}}\left({anti_u_ltx}\right)",
                    after_latex=h_u_ltx,
                ),
            ]
        )
    else:
        step6_substeps.extend(
            [
                EducationalStep(
                    step_id=f"SUB_06_1_{tag}",
                    rule_name="Identificar regla elemental en u",
                    explanation=(
                        f"Aplicamos la regla elemental sobre \\({h_u_ltx}\\) "
                        f"para obtener \\({anti_u_ltx}\\)."
                    ),
                    before_latex=rf"\int {h_u_ltx}\,du",
                    after_latex=anti_u_ltx,
                ),
                EducationalStep(
                    step_id=f"SUB_06_2_{tag}",
                    rule_name="Derivar respecto de u para comprobar",
                    explanation=(
                        f"Comprobamos que \\(\\frac{{d}}{{du}}"
                        f"\\left({anti_u_ltx}\\right) = {h_u_ltx}\\)."
                    ),
                    before_latex=rf"\frac{{d}}{{du}}\left({anti_u_ltx}\right)",
                    after_latex=h_u_ltx,
                ),
            ]
        )

    step_6 = EducationalStep(
        step_id=f"SUB_06_{tag}",
        rule_name="Integración transformada",
        explanation=(
            f"Integramos respecto de \\(u\\) la expresión \\(\\int {h_u_ltx}\\,du\\) "
            f"y obtenemos \\({anti_u_ltx}\\)."
        ),
        before_latex=rf"\int {h_u_ltx}\,du",
        after_latex=anti_u_ltx,
        sub_steps=step6_substeps,
    )

    # Paso 7
    if bounds is not None and new_bounds is not None:
        a_ltx = format_math_latex(bounds[0])
        b_ltx = format_math_latex(bounds[1])
        low_u_ltx = format_math_latex(new_bounds[0])
        up_u_ltx = format_math_latex(new_bounds[1])
        step_7 = EducationalStep(
            step_id=f"SUB_07_{tag}",
            rule_name="Retorno o transformación de límites",
            explanation=(
                f"Transformamos los extremos con \\(u = {u_ltx}\\): "
                f"\\(u({a_ltx}) = {low_u_ltx}\\) y \\(u({b_ltx}) = {up_u_ltx}\\)."
            ),
            before_latex=rf"u({a_ltx}) = {low_u_ltx},\quad u({b_ltx}) = {up_u_ltx}",
            after_latex=rf"\left[{anti_u_ltx}\right]_{{{low_u_ltx}}}^{{{up_u_ltx}}}",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_07_1_{tag}",
                    rule_name="Calcular extremos transformados",
                    explanation=(
                        f"Evaluamos \\(u({a_ltx}) = {low_u_ltx}\\) y "
                        f"\\(u({b_ltx}) = {up_u_ltx}\\)."
                    ),
                    before_latex=rf"\left(u({a_ltx}),\,u({b_ltx})\right)",
                    after_latex=rf"\left({low_u_ltx},\,{up_u_ltx}\right)",
                )
            ],
        )
    else:
        step_7 = EducationalStep(
            step_id=f"SUB_07_{tag}",
            rule_name="Retorno o transformación de límites",
            explanation=(
                f"Deshacemos el cambio reemplazando \\(u = {u_ltx}\\) "
                f"en \\({anti_u_ltx}\\) para obtener \\({anti_x_ltx}\\)."
            ),
            before_latex=anti_u_ltx,
            after_latex=anti_x_ltx,
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_07_1_{tag}",
                    rule_name="Restaurar la función interior",
                    explanation=f"Sustituimos \\(u\\) por \\({u_ltx}\\).",
                    before_latex=anti_u_ltx,
                    after_latex=anti_x_ltx,
                )
            ],
        )

    # Paso 8
    if bounds is not None and new_bounds is not None and definite_value is not None:
        low_u_ltx = format_math_latex(new_bounds[0])
        up_u_ltx = format_math_latex(new_bounds[1])
        def_val_ltx = format_math_latex(definite_value)
        step_8 = EducationalStep(
            step_id=f"SUB_08_{tag}",
            rule_name="Constante de integración o evaluación",
            explanation=(
                "Aplicamos el Teorema Fundamental del Cálculo evaluando en "
                f"\\(u = {up_u_ltx}\\) y \\(u = {low_u_ltx}\\): \\({def_val_ltx}\\)."
            ),
            before_latex=rf"\left[{anti_u_ltx}\right]_{{{low_u_ltx}}}^{{{up_u_ltx}}}",
            after_latex=def_val_ltx,
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_08_1_{tag}",
                    rule_name="Aplicar teorema fundamental",
                    explanation=(
                        f"Calculamos \\(F({up_u_ltx}) - F({low_u_ltx}) = "
                        f"{def_val_ltx}\\)."
                    ),
                    before_latex=(
                        rf"\left[{anti_u_ltx}\right]_{{{low_u_ltx}}}^{{{up_u_ltx}}}"
                    ),
                    after_latex=def_val_ltx,
                )
            ],
        )
    else:
        step_8 = EducationalStep(
            step_id=f"SUB_08_{tag}",
            rule_name="Constante de integración",
            explanation=(
                "Por tratarse de una integral indefinida, añadimos la "
                f"constante arbitraria \\(C\\): \\({anti_x_ltx} + C\\)."
            ),
            before_latex=anti_x_ltx,
            after_latex=f"{anti_x_ltx} + C",
            sub_steps=[
                EducationalStep(
                    step_id=f"SUB_08_1_{tag}",
                    rule_name="Expresar familia de primitivas",
                    explanation=(
                        "Añadimos \\(C\\) en cada componente conexa del dominio."
                    ),
                    before_latex=anti_x_ltx,
                    after_latex=f"{anti_x_ltx} + C",
                )
            ],
        )

    # Paso 9
    step_9 = EducationalStep(
        step_id=f"SUB_09_{tag}",
        rule_name="Verificación de la igualdad",
        explanation=(
            f"Comprobamos por derivación que \\(\\frac{{d}}{{d{var_ltx}}}"
            f"\\left({anti_x_ltx}\\right) = {expr_ltx}\\) bajo \\({domain_latex}\\)."
        ),
        before_latex=rf"\frac{{d}}{{d{var_ltx}}}\left({anti_x_ltx}\right)",
        after_latex=expr_ltx,
        sub_steps=[
            EducationalStep(
                step_id=f"SUB_09_1_{tag}",
                rule_name="Simplificar residual simbólico",
                explanation=(
                    f"La diferencia \\(\\frac{{d}}{{d{var_ltx}}}({anti_x_ltx}) "
                    f"- ({expr_ltx})\\) se simplifica a \\(0\\)."
                ),
                before_latex=(
                    rf"\frac{{d}}{{d{var_ltx}}}\left({anti_x_ltx}\right) "
                    rf"- \left({expr_ltx}\right)"
                ),
                after_latex="0",
            ),
            EducationalStep(
                step_id=f"SUB_09_2_{tag}",
                rule_name="Marcar estado de validación",
                explanation=(
                    "La ruta de sustitución queda certificada con residuo \\(0\\)."
                ),
                before_latex="0",
                after_latex=r"0\quad\text{(verificado)}",
            ),
        ],
    )

    return (
        step_1,
        step_2,
        step_3,
        step_4,
        step_5,
        step_6,
        step_7,
        step_8,
        step_9,
    )


def _try_direct_or_constant_substitution(
    expr: sp.Expr,
    var: sp.Symbol,
    u_sym: sp.Symbol,
    bounds: tuple[sp.Expr, sp.Expr] | None,
) -> SubstitutionAnalysis | None:
    """Evalúa sustitución directa, ajuste constante, anidada y logarítmica."""
    candidates = candidate_subexpressions(expr, var)
    best: tuple[int, SubstitutionAnalysis] | None = None

    for g in candidates:
        dg = sp.diff(g, var)
        if dg == 0:
            continue
        raw_q = expr / dg
        h_u = raw_q.subs(g, u_sym)
        if var in h_u.free_symbols:
            h_u = sp.factor_terms(raw_q).subs(g, u_sym)
        if var in h_u.free_symbols:
            h_u = sp.cancel(sp.together(raw_q)).subs(g, u_sym)
        if var in h_u.free_symbols:
            continue
        residual_change = sp.simplify(h_u.subs(u_sym, g) * dg - expr)
        if residual_change != 0:
            continue

        indep_k, dep_u = h_u.as_independent(u_sym, as_Add=False)
        const_factor = sp.simplify(indep_k) if dep_u != 1 else sp.Integer(1)

        antideriv_u, is_log_abs = _integrate_in_u_safely(h_u, u_sym)
        if antideriv_u is None:
            continue

        antideriv_x = antideriv_u.subs(u_sym, g)
        proof_res = _verify_derivative_identity(antideriv_x, expr, var)
        if proof_res != 0:
            continue

        var_ltx = format_math_latex(var)
        domain_ltx = rf"{var_ltx} \in \mathbb{{R}}"
        assumptions: list[str] = []
        if bounds is not None:
            method_id = "SUB_DEFINITE_BOUNDS"
            b0_ltx = format_math_latex(bounds[0])
            b1_ltx = format_math_latex(bounds[1])
            domain_ltx = rf"{b0_ltx} \le {var_ltx} \le {b1_ltx}"
        elif is_log_abs:
            method_id = "SUB_LOG_ABSOLUTE"
            zeros = sp.solve(g, var)
            if zeros:
                z_ltx = ", ".join(format_math_latex(z) for z in zeros)
                domain_ltx = rf"{var_ltx} \neq {z_ltx}"
                assumptions.append(f"{var} != {zeros}")
        elif _has_nested_composition(g, var):
            method_id = "SUB_NESTED"
        elif const_factor == 1:
            method_id = "SUB_EXACT"
        else:
            method_id = "SUB_CONSTANT_FACTOR"

        new_bounds: tuple[sp.Expr, sp.Expr] | None = None
        definite_value: sp.Expr | None = None
        if bounds is not None:
            low_u = sp.simplify(g.subs(var, bounds[0]))
            up_u = sp.simplify(g.subs(var, bounds[1]))
            new_bounds = (low_u, up_u)
            definite_value = sp.simplify(
                antideriv_u.subs(u_sym, up_u) - antideriv_u.subs(u_sym, low_u)
            )

        nested_penalty = 10 if _has_nested_composition(dep_u, u_sym) else 0
        ops_score = int(sp.count_ops(dep_u)) + nested_penalty

        steps = _build_standard_9_steps(
            tag=method_id,
            method_id=method_id,
            expr=expr,
            var=var,
            u_sym=u_sym,
            u_expr=g,
            du_dx=dg,
            const_factor=const_factor,
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            domain_latex=domain_ltx,
            bounds=bounds,
            new_bounds=new_bounds,
            definite_value=definite_value,
            is_log_abs=is_log_abs,
        )

        analysis = SubstitutionAnalysis(
            method_id=method_id,
            u_expr=g,
            du_dx=dg,
            const_factor=const_factor,
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            proof_residual=proof_res,
            status="verified",
            domain_latex=domain_ltx,
            original_bounds=bounds,
            new_bounds=new_bounds,
            definite_value=definite_value,
            assumptions=tuple(assumptions),
            steps=steps,
        )
        if best is None or ops_score < best[0]:
            best = (ops_score, analysis)

    return best[1] if best is not None else None


def _try_inverse_affine_substitution(
    expr: sp.Expr,
    var: sp.Symbol,
    u_sym: sp.Symbol,
    bounds: tuple[sp.Expr, sp.Expr] | None,
) -> SubstitutionAnalysis | None:
    """Detecta y resuelve SUB_INVERSE_AFFINE (despeje de x en u = ax + b)."""
    for g in candidate_subexpressions(expr, var):
        dg = sp.diff(g, var)
        if dg == 0 or dg.has(var):
            continue
        sols = sp.solve(sp.Eq(u_sym, g), var)
        if len(sols) != 1:
            continue
        x_of_u = sols[0]
        dx_du = sp.diff(x_of_u, u_sym)

        unexpanded_u = expr.subs(g, u_sym).subs(var, x_of_u) * dx_du
        if var in unexpanded_u.free_symbols:
            continue
        h_u = sp.expand(unexpanded_u)
        if var in h_u.free_symbols:
            continue

        residual_change = sp.simplify(h_u.subs(u_sym, g) * dg - expr)
        if residual_change != 0:
            continue

        antideriv_u, _ = _integrate_in_u_safely(h_u, u_sym)
        if antideriv_u is None:
            continue
        antideriv_x = antideriv_u.subs(u_sym, g)
        proof_res = _verify_derivative_identity(antideriv_x, expr, var)
        if proof_res != 0:
            continue

        var_ltx = format_math_latex(var)
        domain_ltx = rf"{var_ltx} \in \mathbb{{R}}"
        assumptions: list[str] = []
        for node in sp.preorder_traversal(expr):
            if (
                isinstance(node, sp.Pow)
                and node.base == g
                and node.exp.is_Rational
                and node.exp.q % 2 == 0
            ):
                bound_x = sp.solve(g, var)
                if bound_x:
                    b_ltx = format_math_latex(bound_x[0])
                    domain_ltx = rf"{var_ltx} \ge {b_ltx}"
                    assumptions.append(f"{var} >= {bound_x[0]}")

        new_bounds: tuple[sp.Expr, sp.Expr] | None = None
        definite_value: sp.Expr | None = None
        if bounds is not None:
            low_u = sp.simplify(g.subs(var, bounds[0]))
            up_u = sp.simplify(g.subs(var, bounds[1]))
            new_bounds = (low_u, up_u)
            definite_value = sp.simplify(
                antideriv_u.subs(u_sym, up_u) - antideriv_u.subs(u_sym, low_u)
            )

        steps = _build_standard_9_steps(
            tag="SUB_INVERSE_AFFINE",
            method_id="SUB_INVERSE_AFFINE",
            expr=expr,
            var=var,
            u_sym=u_sym,
            u_expr=g,
            du_dx=dg,
            const_factor=sp.Integer(1),
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            domain_latex=domain_ltx,
            x_of_u=x_of_u,
            dx_du=dx_du,
            unexpanded_in_u=unexpanded_u,
            bounds=bounds,
            new_bounds=new_bounds,
            definite_value=definite_value,
        )
        return SubstitutionAnalysis(
            method_id="SUB_INVERSE_AFFINE",
            u_expr=g,
            du_dx=dg,
            const_factor=sp.Integer(1),
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            proof_residual=proof_res,
            status="verified",
            domain_latex=domain_ltx,
            x_of_u=x_of_u,
            dx_du=dx_du,
            original_bounds=bounds,
            new_bounds=new_bounds,
            definite_value=definite_value,
            assumptions=tuple(assumptions),
            steps=steps,
        )
    return None


def _try_complete_square_substitution(
    expr: sp.Expr,
    var: sp.Symbol,
    u_sym: sp.Symbol,
    bounds: tuple[sp.Expr, sp.Expr] | None,
) -> SubstitutionAnalysis | None:
    """Detecta trinomios cuadráticos ax^2 + bx + c y aplica SUB_COMPLETE_SQUARE."""
    for cand in candidate_subexpressions(expr, var):
        try:
            poly = sp.Poly(cand, var)
        except sp.PolynomialError:
            continue
        if poly.degree() != 2:
            continue
        a_coeff, b_coeff, c_coeff = poly.all_coeffs()
        if a_coeff == 0 or b_coeff == 0:
            continue
        if any(coeff.has(var) for coeff in (a_coeff, b_coeff, c_coeff)):
            continue

        shift = sp.simplify(b_coeff / (2 * a_coeff))
        g = var + shift
        rem = sp.simplify(c_coeff - b_coeff**2 / (4 * a_coeff))
        if rem == 0:
            continue
        completed_q = a_coeff * g**2 + rem
        if sp.expand(completed_q - cand) != 0:
            continue

        dg = sp.Integer(1)
        x_of_u = u_sym - shift
        dx_du = sp.Integer(1)
        quad_in_u = a_coeff * u_sym**2 + rem
        h_u = sp.together(expr.subs(cand, quad_in_u).subs(var, x_of_u))
        if var in h_u.free_symbols:
            continue

        if a_coeff == 1 and rem > 0:
            a_val = sp.sqrt(rem)
            num_u = sp.simplify(h_u * sp.sqrt(u_sym**2 + rem))
            poly_num = sp.Poly(num_u, u_sym) if num_u.is_polynomial(u_sym) else None
            if poly_num is not None and poly_num.degree() <= 1:
                c1 = poly_num.nth(1)
                c0 = poly_num.nth(0)
                antideriv_u = c1 * sp.sqrt(u_sym**2 + rem) + c0 * sp.asinh(
                    u_sym / a_val
                )
            else:
                antideriv_u, _ = _integrate_in_u_safely(h_u, u_sym)
        else:
            antideriv_u, _ = _integrate_in_u_safely(h_u, u_sym)

        if antideriv_u is None:
            continue

        antideriv_x = antideriv_u.subs(u_sym**2 + rem, cand).subs(u_sym, g)
        proof_res = _verify_derivative_identity(antideriv_x, expr, var)
        if proof_res != 0:
            continue

        domain_ltx = rf"{format_math_latex(var)} \in \mathbb{{R}}"
        steps = _build_standard_9_steps(
            tag="SUB_COMPLETE_SQUARE",
            method_id="SUB_COMPLETE_SQUARE",
            expr=expr,
            var=var,
            u_sym=u_sym,
            u_expr=g,
            du_dx=dg,
            const_factor=sp.Integer(1),
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            domain_latex=domain_ltx,
            x_of_u=x_of_u,
            dx_du=dx_du,
            completed_quadratic=completed_q,
            original_quadratic=cand,
            bounds=bounds,
        )
        return SubstitutionAnalysis(
            method_id="SUB_COMPLETE_SQUARE",
            u_expr=g,
            du_dx=dg,
            const_factor=sp.Integer(1),
            integrand_in_u=h_u,
            antideriv_in_u=antideriv_u,
            antideriv_in_x=antideriv_x,
            proof_residual=proof_res,
            status="verified",
            domain_latex=domain_ltx,
            x_of_u=x_of_u,
            dx_du=dx_du,
            completed_quadratic=completed_q,
            original_quadratic=cand,
            original_bounds=bounds,
            steps=steps,
        )
    return None


def _build_rejected_substitution(
    expr: sp.Expr,
    var: sp.Symbol,
    u_sym: sp.Symbol,
    cand_g: sp.Expr,
) -> SubstitutionAnalysis:
    """Construye el diagnóstico honesto SUB_REJECTED cuando falla la sustitución."""
    dg = sp.diff(cand_g, var)
    quotient = sp.cancel(sp.together(expr / dg)) if dg != 0 else expr
    partial_u = quotient.subs(cand_g, u_sym)

    var_ltx = format_math_latex(var)
    expr_ltx = format_math_latex(expr)
    g_ltx = format_math_latex(cand_g)
    dg_ltx = format_math_latex(dg)
    partial_ltx = format_math_latex(partial_u)

    oracle = sp.integrate(expr, var)
    has_special = not oracle.has(sp.Integral)
    oracle_ltx = format_math_latex(oracle)

    steps = (
        EducationalStep(
            step_id="SUB_01_T08",
            rule_name="Examinar composición candidata",
            explanation=(
                f"Detectamos la expresión interior \\({g_ltx}\\) en "
                f"\\({expr_ltx}\\); por sí sola no garantiza una sustitución útil."
            ),
            before_latex=rf"\int {expr_ltx}\,d{var_ltx}",
            after_latex=rf"u = {g_ltx}\quad\text{{(candidato)}}",
        ),
        EducationalStep(
            step_id="SUB_02_T08",
            rule_name="Derivar el candidato",
            explanation=(
                f"La elección \\(u = {g_ltx}\\) produce "
                f"\\(du = {dg_ltx}\\,d{var_ltx}\\)."
            ),
            before_latex=f"u = {g_ltx}",
            after_latex=rf"du = {dg_ltx}\,d{var_ltx}",
        ),
        EducationalStep(
            step_id="SUB_03_T08",
            rule_name="Comprobar factores diferenciales",
            explanation=(
                f"El integrando \\({expr_ltx}\\) no incluye el factor "
                f"\\({dg_ltx}\\) necesario para cambiar directamente a \\(du\\)."
            ),
            before_latex=rf"{expr_ltx}\,d{var_ltx}",
            after_latex=(
                rf"{partial_ltx}\,du\quad"
                rf"\text{{(todavía depende de }}{var_ltx}\text{{)}}"
            ),
        ),
        EducationalStep(
            step_id="SUB_04_T08",
            rule_name="Rechazar ruta de sustitución simple",
            explanation=(
                f"La condición \\({var_ltx} \\notin "
                "\\operatorname{free\\_symbols}(h_u)\\) falla; no puede "
                "expresarse como integral elemental en una sola variable \\(u\\)."
            ),
            before_latex=rf"{partial_ltx}\,du",
            after_latex=r"\text{Sustitución elemental simple no aplicable}",
        ),
        EducationalStep(
            step_id="SUB_05_T08",
            rule_name="Ofrecer una salida honesta",
            explanation=(
                f"No existe una primitiva elemental por sustitución simple "
                f"para \\({expr_ltx}\\). "
                + (
                    f"Con funciones especiales resulta \\({oracle_ltx} + C\\)."
                    if has_special
                    else "Se requiere otro método de integración."
                )
            ),
            before_latex=rf"\int {expr_ltx}\,d{var_ltx}",
            after_latex=(
                rf"{oracle_ltx} + C\quad\text{{(función especial)}}"
                if has_special
                else rf"\int {expr_ltx}\,d{var_ltx}"
            ),
        ),
    )

    return SubstitutionAnalysis(
        method_id="SUB_REJECTED",
        u_expr=cand_g,
        du_dx=dg,
        const_factor=sp.Integer(1),
        integrand_in_u=partial_u,
        antideriv_in_u=oracle,
        antideriv_in_x=oracle,
        proof_residual=sp.Integer(1),
        status="rejected",
        steps=steps,
    )


def analyze_substitution(
    expr_or_integral: sp.Expr,
    var: sp.Symbol | None = None,
    bounds: tuple[sp.Expr, sp.Expr] | None = None,
) -> SubstitutionAnalysis | None:
    """Punto de entrada principal del motor de integración por sustitución."""
    expr = expr_or_integral
    if isinstance(expr_or_integral, sp.Integral):
        expr = expr_or_integral.function
        if expr_or_integral.limits:
            lim = expr_or_integral.limits[0]
            if var is None and isinstance(lim[0], sp.Symbol):
                var = lim[0]
            if len(lim) == 3 and bounds is None:
                bounds = (sp.sympify(lim[1]), sp.sympify(lim[2]))

    if var is None:
        free = sorted(expr.free_symbols, key=lambda s: s.name)
        var = free[0] if free else sp.Symbol("x", real=True)

    if bounds is None and _is_direct_elementary_in_var(expr, var):
        return None

    u_sym = sp.Symbol("u", real=True)

    direct = _try_direct_or_constant_substitution(expr, var, u_sym, bounds)
    if direct is not None:
        return direct

    inverse_affine = _try_inverse_affine_substitution(expr, var, u_sym, bounds)
    if inverse_affine is not None:
        return inverse_affine

    complete_sq = _try_complete_square_substitution(expr, var, u_sym, bounds)
    if complete_sq is not None:
        return complete_sq

    candidates = candidate_subexpressions(expr, var)
    if candidates:
        return _build_rejected_substitution(expr, var, u_sym, candidates[0])

    return None
