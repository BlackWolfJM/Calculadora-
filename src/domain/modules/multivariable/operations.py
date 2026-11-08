import sympy as sp

from src.domain.domain_checks import require_real_finite, validate_point
from src.domain.modules.multivariable.support import (
    _safe_number,
    require_identifier,
    require_variables,
    response,
    step,
)
from src.domain.responses import SolutionResponse
from src.domain.steps import EducationalStep, StepCoverage


def solve_multivariable_value(expression, parameters, adapter) -> SolutionResponse:
    """Evalúa una función multivariable en un punto."""
    expr = adapter.ast_to_sympy(expression)
    names = require_variables(parameters.get("variables"), dimensions=(2, 3, 4, 5))
    point = parameters.get("point")

    if not isinstance(point, dict) or set(point) != set(names):
        raise ValueError(
            "point debe asignar exactamente todas las variables declaradas."
        )

    substitution = {sp.Symbol(v, real=True): _safe_number(point[v]) for v in names}

    if expr.free_symbols - set(substitution):
        raise ValueError("Faltan valores para variables libres de la función.")

    validate_point(expression, substitution, adapter)
    result = sp.simplify(expr.subs(substitution))

    if result.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or result.is_real is False:
        raise ValueError("El punto está fuera del dominio real de la función.")

    return response(
        "Valor de la función",
        result,
        [
            step(
                "mv-substitute",
                "Sustitución del punto",
                "Se reemplaza cada variable por su coordenada.",
                expr,
                result,
            )
        ],
        verification=None,
    )


def solve_partial(
    expression, parameters, adapter, derivative_steps
) -> SolutionResponse:
    """Calcula la derivada parcial respecto a una variable."""
    name = require_identifier(parameters.get("variable", "x"), field="variable")
    order = parameters.get("order", 1)

    if isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= 5:
        raise ValueError("order debe ser un entero entre 1 y 5.")

    expr = adapter.ast_to_sympy(expression)
    var = sp.Symbol(name, real=True)
    result = sp.simplify(adapter.diff(expr, var, order))

    # Intentamos obtener pasos educativos si el motor los soporta
    generated = derivative_steps.generate_steps(expr, var, order)

    diff_check = sp.simplify(sp.diff(expr, var, order) - result)
    return response(
        "Derivada parcial",
        result,
        generated.steps,
        coverage=generated.coverage,
        verification=f"diff(expr, {name}, {order}) - resultado = {diff_check}",
    )


def solve_gradient(
    expression, parameters, adapter, derivative_steps
) -> SolutionResponse:
    """Calcula el vector gradiente."""
    names = require_variables(parameters.get("variables"), dimensions=(2, 3))
    expr = adapter.ast_to_sympy(expression)
    variables = tuple(sp.Symbol(n, real=True) for n in names)

    components, substeps, coverage = [], [], StepCoverage.COMPLETE

    for var in variables:
        components.append(sp.simplify(adapter.diff(expr, var)))
        generated = derivative_steps.generate_steps(expr, var, 1)
        substeps.extend(generated.steps)
        if generated.coverage is not StepCoverage.COMPLETE:
            coverage = StepCoverage.PARTIAL

    result = sp.Matrix(components)

    top = EducationalStep(
        "gradient",
        "Construir el gradiente",
        "Se deriva una vez respecto de cada variable, en el orden declarado.",
        sp.latex(expr),
        sp.latex(result),
        sub_steps=substeps,
    )

    return response("Gradiente", result, [top], coverage=coverage, verification=None)


def solve_directional(
    expression, parameters, adapter, derivative_steps
) -> SolutionResponse:
    """Calcula la derivada direccional en un punto dado."""
    names = require_variables(parameters.get("variables"), dimensions=(2, 3))
    raw_direction = parameters.get("direction")
    point = parameters.get("point")

    if not isinstance(raw_direction, (list, tuple)) or len(raw_direction) != len(names):
        raise ValueError(
            f"direction debe ser un arreglo numérico de dimensión {len(names)}."
        )
    if not isinstance(point, dict) or set(point) != set(names):
        raise ValueError("point debe asignar exactamente las variables declaradas.")

    variables = tuple(sp.Symbol(n, real=True) for n in names)
    expr = adapter.ast_to_sympy(expression)

    direction = sp.Matrix([_safe_number(x) for x in raw_direction])

    norm = sp.sqrt(direction.dot(direction))
    if norm.is_zero is not False:
        raise ValueError("La dirección debe ser no nula.")

    unit = sp.simplify(direction / norm)
    substitution = {v: _safe_number(point[str(v)]) for v in variables}

    validate_point(expression, substitution, adapter)
    t = sp.Dummy("t", real=True)
    along = expr.subs(
        {v: substitution[v] + t * unit[i] for i, v in enumerate(variables)},
        simultaneous=True,
    )
    quotient = (along - expr.subs(substitution, simultaneous=True)) / t
    left = sp.limit(quotient, t, 0, dir="-")
    right = sp.limit(quotient, t, 0, dir="+")
    require_real_finite(left)
    require_real_finite(right)
    if sp.simplify(left - right) != 0:
        raise ValueError("La derivada direccional bilateral no existe en ese punto.")

    result = sp.simplify(right)

    return response(
        "Derivada direccional",
        result,
        [
            step(
                "dir-unit",
                "Dirección unitaria",
                "Se normaliza la dirección.",
                direction,
                unit,
            ),
            step(
                "dir-limit",
                "Definición por límite bilateral",
                (
                    "Se evalúa el cociente incremental sobre la recta y se "
                    "comparan ambos límites laterales."
                ),
                sp.Limit(quotient, t, 0),
                result,
            ),
        ],
        verification="Los límites laterales son reales, finitos e iguales.",
    )


def solve_laplacian(
    expression, parameters, adapter, derivative_steps
) -> SolutionResponse:
    """Calcula el Laplaciano (divergencia del gradiente)."""
    names = require_variables(parameters.get("variables"), dimensions=(2, 3))
    expr = adapter.ast_to_sympy(expression)
    variables = tuple(sp.Symbol(n, real=True) for n in names)

    components = []
    substeps = []
    coverage = StepCoverage.COMPLETE

    for index, var in enumerate(variables):
        second_derivative = sp.simplify(adapter.diff(expr, var, 2))
        components.append(second_derivative)

        # Intentar adjuntar los pasos de la segunda derivada si se soportan
        generated = derivative_steps.generate_steps(expr, var, 2)
        substeps.extend(generated.steps)
        if generated.coverage is not StepCoverage.COMPLETE:
            coverage = StepCoverage.PARTIAL

    result = sp.simplify(sum(components))

    top = EducationalStep(
        "laplacian",
        "Suma de segundas derivadas (Laplaciano)",
        "Se calcula la segunda derivada respecto a cada variable y se suman.",
        sp.latex(expr),
        sp.latex(result),
        sub_steps=substeps,
    )

    return response("Laplaciano", result, [top], coverage=coverage, verification=None)
