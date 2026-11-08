"""Operaciones con listas de expresiones, matrices y coordenadas."""

from collections.abc import Callable
from dataclasses import dataclass

import sympy as sp
from sympy.calculus.util import continuous_domain

from src.domain.expressions.ast_nodes import ExpressionNode, ListLiteral
from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.steps import EducationalStep, StepCoverage, StepOutcome, StepStatus
from src.infrastructure.sympy_adapter import SympyAdapter

X, Y, Z = sp.symbols("x y z", real=True)


@dataclass(frozen=True)
class WorkedResult:
    value: sp.Basic | sp.MatrixBase
    rule: str
    explanation: str
    formula: str
    verification: str | None = None
    warnings: tuple[str, ...] = ()


def _items(value, count: int):
    if not isinstance(value, tuple) or len(value) != count:
        raise ValueError(f"Se requiere una lista de {count} elementos.")
    return value


def _scalar(value, variables=frozenset()):
    if (
        not isinstance(value, sp.Expr)
        or value.free_symbols - variables
        or value.has(sp.nan, sp.zoo, sp.oo, -sp.oo, sp.I)
    ):
        raise ValueError("Usa expresiones finitas con las variables indicadas.")
    return value


def _real(value):
    value = _scalar(value)
    if value.is_real is not True or value.is_finite is not True:
        raise ValueError("Se requieren números reales finitos.")
    return value


def _definite(value):
    f, lower, upper = _items(value, 3)
    f = _scalar(f, {X})
    lower, upper = _real(lower), _real(upper)
    if lower == upper:
        _real(f.subs(X, lower))
    else:
        interval = sp.Interval(sp.Min(lower, upper), sp.Max(lower, upper))
        if interval.is_subset(continuous_domain(f, X, sp.S.Reals)) is not True:
            raise ValueError("Se requiere una función continua entre los límites.")
    integral = sp.Integral(f, (X, lower, upper))
    result = integral.doit()
    if result.has(sp.Integral):
        raise NotImplementedError
    return WorkedResult(
        _real(result),
        "Teorema fundamental del cálculo",
        "Integramos en x y evaluamos la antiderivada en el límite superior "
        "menos su valor en el límite inferior.",
        rf"{sp.latex(integral)} = F({sp.latex(upper)})-F({sp.latex(lower)})",
    )


def _field(value, curl: bool):
    p, q, r = [_scalar(item, {X, Y, Z}) for item in _items(value, 3)]
    if curl:
        result = sp.Tuple(
            r.diff(Y) - q.diff(Z), p.diff(Z) - r.diff(X), q.diff(X) - p.diff(Y)
        )
        return WorkedResult(
            result,
            "Rotacional",
            "Restamos las derivadas cruzadas de las componentes P, Q y R "
            "en el orden del producto cruz.",
            r"\nabla\times\mathbf F=(R_y-Q_z,\;P_z-R_x,\;Q_x-P_y)",
        )
    return WorkedResult(
        p.diff(X) + q.diff(Y) + r.diff(Z),
        "Divergencia",
        "Derivamos cada componente del campo respecto a su coordenada y sumamos.",
        r"\nabla\cdot\mathbf F=P_x+Q_y+R_z",
    )


def _linear_ode(value):
    a, b = [_scalar(item, {X}) for item in _items(value, 2)]
    if any(continuous_domain(f, X, sp.S.Reals) != sp.S.Reals for f in (a, b)):
        raise ValueError("Los coeficientes deben ser continuos para todo x real.")
    primitive = sp.integrate(a, X)
    if primitive.has(sp.Integral):
        raise NotImplementedError
    factor = sp.exp(primitive)
    integral = sp.integrate(factor * b, X)
    if integral.has(sp.Integral):
        raise NotImplementedError
    solution = sp.simplify((integral + sp.Symbol("C")) / factor)
    y = sp.Function("y")
    verified = sp.simplify(solution.diff(X) + a * solution - b) == 0
    return WorkedResult(
        sp.Eq(y(X), solution),
        "Factor integrante",
        "Multiplicamos la ecuación por μ. El lado izquierdo se convierte en "
        "la derivada de μy. Integramos ambos lados y dividimos por μ. "
        "C es una constante arbitraria.",
        rf"\mu=e^{{\int a(x)\,dx}}={sp.latex(factor)},"
        r"\quad (\mu y)'=\mu b(x)",
        "Verificado matemáticamente con éxito." if verified else None,
        () if verified else ("No se pudo comprobar la ecuación por sustitución.",),
    )


def _positive(value):
    value = _real(value)
    if value.is_positive is not True:
        raise ValueError("Las longitudes deben ser positivas.")
    return value


def _circle_area(value):
    (radius,) = map(_positive, _items(value, 1))
    return WorkedResult(
        sp.pi * radius**2,
        "Área del círculo",
        "Multiplicamos el cuadrado del radio por π.",
        rf"A=\pi\left({sp.latex(radius)}\right)^2",
    )


def _triangle_area(value):
    a, b, c = map(_positive, _items(value, 3))
    s = (a + b + c) / 2
    if any((s - side).is_positive is not True for side in (a, b, c)):
        raise ValueError("La suma de cada par de lados debe superar al tercer lado.")
    return WorkedResult(
        sp.sqrt(s * (s - a) * (s - b) * (s - c)),
        "Fórmula de Herón",
        "Sumamos los lados y dividimos por dos para obtener s. "
        "Aplicamos la raíz cuadrada al producto de s y las tres diferencias.",
        rf"s={sp.latex(s)},\quad A=\sqrt{{s(s-a)(s-b)(s-c)}}",
    )


def _points(value):
    first, second = _items(value, 2)
    return tuple(tuple(map(_real, _items(point, 2))) for point in (first, second))


def _distance(value):
    (x1, y1), (x2, y2) = _points(value)
    dx, dy = x2 - x1, y2 - y1
    return WorkedResult(
        sp.sqrt(dx**2 + dy**2),
        "Distancia euclídea",
        "Restamos las coordenadas correspondientes. Aplicamos Pitágoras "
        "a las diferencias horizontal y vertical.",
        rf"d=\sqrt{{\left({sp.latex(dx)}\right)^2+\left({sp.latex(dy)}\right)^2}}",
    )


def _midpoint(value):
    (x1, y1), (x2, y2) = _points(value)
    return WorkedResult(
        sp.Tuple((x1 + x2) / 2, (y1 + y2) / 2),
        "Punto medio",
        "Promediamos por separado las coordenadas x e y.",
        r"M=\left(\frac{x_1+x_2}{2},\frac{y_1+y_2}{2}\right)",
    )


def _line(value):
    (x1, y1), (x2, y2) = _points(value)
    dx, dy = x2 - x1, y2 - y1
    if dx.is_zero and dy.is_zero:
        raise ValueError("Se requieren dos puntos distintos para definir la recta.")
    return WorkedResult(
        sp.Eq(sp.expand(dy * (X - x1) - dx * (Y - y1)), 0),
        "Recta por dos puntos",
        "El desplazamiento desde el primer punto debe ser paralelo "
        "al vector que une los dos puntos.",
        r"(y_2-y_1)(x-x_1)-(x_2-x_1)(y-y_1)=0",
    )


def _count(value, ordered: bool):
    n, k = map(_real, _items(value, 2))
    if not all(v.is_Integer for v in (n, k)) or not 0 <= k <= n <= 100:
        raise ValueError("Usa enteros que cumplan 0 ≤ k ≤ n ≤ 100.")
    if ordered:
        return WorkedResult(
            sp.factorial(n) / sp.factorial(n - k),
            "Variaciones sin repetición",
            "Elegimos k de n elementos distintos. Cada posición tiene una "
            "opción menos que la anterior.",
            rf"P({n},{k})=\frac{{{n}!}}{{{n - k}!}}",
        )
    return WorkedResult(
        sp.binomial(n, k),
        "Combinaciones sin repetición",
        "Dividimos las selecciones ordenadas entre k! porque cada grupo "
        "de k elementos se puede ordenar de k! maneras.",
        rf"\binom{{{n}}}{{{k}}}=\frac{{{n}!}}{{{k}!\,{n - k}!}}",
    )


def _gcd(value):
    a, b = map(_real, _items(value, 2))
    if not (a.is_Integer and b.is_Integer):
        raise ValueError("Se requieren dos números enteros.")
    return WorkedResult(
        sp.gcd(a, b),
        "Algoritmo de Euclides",
        "Usamos los valores absolutos y sustituimos cada par por el divisor "
        "y el resto hasta que el resto sea cero.",
        rf"\operatorname{{mcd}}({sp.latex(a)}, {sp.latex(b)})",
    )


OPERATIONS: dict[str, dict[str, Callable[..., WorkedResult]]] = {
    "definite_integrals": {"definite": _definite},
    "vector_calculus": {
        "divergence": lambda value: _field(value, curl=False),
        "curl": lambda value: _field(value, curl=True),
    },
    "ode": {"linear": _linear_ode},
    "geometry": {"circle_area": _circle_area, "triangle_area": _triangle_area},
    "analytic_geometry": {"distance": _distance, "midpoint": _midpoint, "line": _line},
    "discrete": {
        "combinations": lambda value: _count(value, ordered=False),
        "permutations": lambda value: _count(value, ordered=True),
        "gcd": _gcd,
    },
}


class StructuredModule:
    def __init__(self, module_id: str, adapter: SympyAdapter) -> None:
        self.module_id = module_id
        self.adapter = adapter
        self.operations = OPERATIONS[module_id]

    def get_id(self) -> str:
        return self.module_id

    def _convert(self, expression: ExpressionNode):
        if isinstance(expression, ListLiteral):
            return tuple(self._convert(item) for item in expression.items)
        return self.adapter.ast_to_sympy(expression)

    def solve(self, expression: ExpressionNode, parameters: dict) -> SolutionResponse:
        operation = parameters.get("operation", next(iter(self.operations)))
        handler = self.operations.get(operation) if isinstance(operation, str) else None
        if handler is None:
            return SolutionResponse(
                response_id="",
                status=ResolutionStatus.UNSUPPORTED,
                error="Operación no disponible en este módulo.",
            )
        try:
            result = handler(self._convert(expression))
        except NotImplementedError:
            return SolutionResponse(
                response_id="",
                status=ResolutionStatus.UNSUPPORTED,
                error="No se pudo obtener una solución para esta entrada.",
            )
        status = (
            ResolutionStatus.SUCCESS_WITH_WARNINGS
            if result.warnings
            else ResolutionStatus.SUCCESS
        )
        latex = sp.latex(result.value, mat_delim="[", mat_str="matrix")
        canonical = str(
            result.value.tolist()
            if isinstance(result.value, sp.MatrixBase)
            else result.value
        )
        return SolutionResponse(
            response_id="",
            status=status,
            calculation=CalculationBlock(
                status.value, ResultItem(MathPayload(canonical, latex), "Resultado")
            ),
            procedure=StepOutcome(
                StepStatus.SUCCESS,
                StepCoverage.COMPLETE,
                [
                    EducationalStep(
                        operation,
                        result.rule,
                        result.explanation,
                        result.formula,
                        latex,
                    )
                ],
            ),
            verification=result.verification,
            warnings=list(result.warnings),
        )
