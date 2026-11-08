"""Bounded offline sampling for the interactive graphing workspace."""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, fields
from functools import lru_cache
from typing import Any, cast

import numpy as np
import sympy as sp  # type: ignore[import-untyped]
from numpy.typing import NDArray

from src.domain.errors import StructuredMathError
from src.domain.expressions.ast_nodes import (
    Divide,
    Equals,
    ExpressionNode,
    NumberLiteral,
    Power,
)
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter

Range = tuple[float, float]
Trace = dict[str, Any]
Point = tuple[float, ...]
Array = NDArray[np.float64]
X, Y, Z, T, R = (sp.Symbol(name, real=True) for name in "xyztr")
AXES = {X, Y, Z, T, R}
PALETTE = ("#216653", "#7951A6", "#B45309", "#176D95", "#9E3C55", "#596A25")
MAX_ROWS = 60
MAX_POINTS = 250
MAX_RANGE = 1e9
MAX_COORDINATE = 1e100
RELATION = re.compile(r"(<=|>=|<|>|=)")
COMMAND = re.compile(r"([a-z]+)\((.*)\)", re.DOTALL)
NAMED_POINT = re.compile(r"([A-Z])\s*=\s*(\(.*\))", re.DOTALL)
COMPARISONS = {
    "<": np.less,
    "<=": np.less_equal,
    ">": np.greater,
    ">=": np.greater_equal,
}


@dataclass
class GraphResult:
    traces: list[Trace] = field(default_factory=list)
    errors: dict[int, str] = field(default_factory=dict)
    parameters: tuple[str, ...] = ()
    details: dict[int, str] = field(default_factory=dict)
    notable_points: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Formula:
    value: sp.Expr
    divisors: tuple[sp.Expr, ...] = ()

    @property
    def symbols(self) -> set[sp.Symbol]:
        return set().union(
            self.value.free_symbols, *(d.free_symbols for d in self.divisors)
        )


@lru_cache(maxsize=1)
def _parser() -> MathParser:
    return MathParser()


def _walk(node: ExpressionNode) -> Iterator[ExpressionNode]:
    yield node
    for item in fields(node):
        child = getattr(node, item.name)
        if isinstance(child, ExpressionNode):
            yield from _walk(child)
        elif isinstance(child, tuple):
            for argument in child:
                if isinstance(argument, ExpressionNode):
                    yield from _walk(argument)


@lru_cache(maxsize=384)
def _formula(source: str) -> Formula:
    # The shared parser validates the AST before SymPy sees it.
    source = re.sub(r"(?<![\d.])\.(?=\d)", "0.", source.strip())
    source = re.sub(r"(?<![A-Za-z])exp\s*\(", "e^(", source)
    node = _parser().parse(source)
    if isinstance(node, Equals):
        raise ValueError("Escribe una expresión a cada lado de la relación.")
    adapter = SympyAdapter()
    divisors = []
    for child in _walk(node):
        if isinstance(child, NumberLiteral) and abs(child.value) > MAX_COORDINATE:
            raise ValueError("Los números deben tener magnitud ≤10¹⁰⁰.")
        if isinstance(child, Power) and not _parser().extract_variables(child.base):
            if any(isinstance(term, Power) for term in _walk(child.base)):
                raise ValueError("Simplifica las potencias numéricas anidadas.")
    value = adapter.ast_to_sympy(node)
    for child in _walk(node):
        if isinstance(child, Divide):
            divisor = adapter.ast_to_sympy(child.right)
        elif isinstance(child, Power):
            exponent = adapter.ast_to_sympy(child.exponent)
            if not exponent.is_negative:
                continue
            divisor = adapter.ast_to_sympy(child.base)
        else:
            continue
        # Positive powers have the same zeros as their base. Keep the sign of
        # that base so even powers also split at poles between sampled points.
        if divisor.is_Pow and divisor.exp.is_positive and divisor.exp.is_integer:
            divisor = divisor.base
        divisors.append(divisor)
    if any(abs(integer) > MAX_COORDINATE for integer in value.atoms(sp.Integer)):
        raise ValueError("Simplifica las potencias numéricas de gran magnitud.")
    return Formula(value, tuple(divisors))


@lru_cache(maxsize=384)
def _compiled(expression: sp.Expr, symbols: tuple[sp.Symbol, ...]) -> Any:
    # lambdify compiles expressions assembled solely from the validated AST.
    return sp.lambdify(symbols, expression, modules="numpy", docstring_limit=0)


def _array(
    expression: sp.Expr,
    variables: Mapping[sp.Symbol, Array | float],
    shape: tuple[int, ...],
) -> Array:
    if expression.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        return np.full(shape, np.nan)
    arguments = tuple(sorted(expression.free_symbols, key=lambda symbol: symbol.name))
    values = _compiled(expression, arguments)(
        *(variables[symbol] for symbol in arguments)
    )
    values = np.asarray(values)
    if values.dtype.kind not in "bifuc":
        values = values.astype(np.complex128)
    real = np.where(np.imag(values) == 0, np.real(values), np.nan)
    return np.broadcast_to(real, shape).astype(float, copy=True)


def _numeric(
    formula: Formula,
    variables: Mapping[sp.Symbol, Array | float],
    shape: tuple[int, ...],
) -> Array:
    with np.errstate(all="ignore"):
        values = _array(formula.value, variables, shape)
        invalid = ~np.isfinite(values)
        for divisor in formula.divisors:
            factors = _array(divisor, variables, shape)
            invalid |= ~np.isfinite(factors) | (factors == 0)
            for axis in range(len(shape)):
                axis_factors = np.moveaxis(factors, axis, -1)
                axis_invalid = np.moveaxis(invalid, axis, -1)
                lower, upper = axis_factors[..., :-1], axis_factors[..., 1:]
                crossing = (
                    np.isfinite(lower)
                    & np.isfinite(upper)
                    & (lower != 0)
                    & (upper != 0)
                    & (np.signbit(lower) != np.signbit(upper))
                )
                axis_invalid[..., 1:] |= crossing
        return np.where(invalid, np.nan, values)


def _json_values(values: Array) -> list[Any]:
    clean = values.astype(object)
    clean[~np.isfinite(values)] = None
    return cast(list[Any], clean.tolist())


def _range(bounds: Range) -> Range:
    lo, hi = bounds
    if not -MAX_RANGE <= lo < hi <= MAX_RANGE:
        raise ValueError("Usa límites crecientes, finitos y dentro de ±10⁹.")
    if hi - lo < 1e-9:
        raise ValueError("El intervalo debe abarcar al menos 10⁻⁹ unidades.")
    return float(lo), float(hi)


def _parts(text: str) -> list[str]:
    depth = 0
    start = 0
    parts = []
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
        if depth < 0:
            raise ValueError("Revisa los paréntesis.")
    if depth:
        raise ValueError("Revisa los paréntesis.")
    parts.append(text[start:].strip())
    if not all(parts):
        raise ValueError("Hay un argumento vacío.")
    return parts


def _tuple_parts(text: str) -> list[str]:
    if not text.startswith("(") or not text.endswith(")"):
        return []
    depth = 0
    for char in text[1:-1]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return []
    return _parts(text[1:-1])


def _degree(expression: sp.Expr) -> int:
    if not expression.has(X):
        return 0
    if expression == X:
        return 1
    if expression.is_Add:
        return max(_degree(term) for term in expression.args)
    if expression.is_Mul:
        return sum(_degree(term) for term in expression.args)
    if expression.is_Pow and expression.exp.is_Integer and expression.exp >= 0:
        return _degree(expression.base) * int(expression.exp)
    raise ValueError("La integral gráfica admite polinomios en x.")


def _zero_set(expression: sp.Expr) -> sp.Expr:
    """Keep real zeros while restoring sign changes for contour sampling."""
    if expression.func == sp.Abs:
        return _zero_set(expression.args[0])
    if expression.is_Pow and expression.exp.is_positive and expression.exp.is_integer:
        # Fractional powers may be undefined for negative bases.
        return _zero_set(expression.base)
    if expression.is_Mul:
        return sp.Mul(*(_zero_set(term) for term in expression.args))
    return expression


def _conditions(text: str) -> tuple[str, list[tuple[Formula, str, Formula]]]:
    if "{" not in text:
        return text, []
    base, suffix = text.split("{", 1)
    groups = re.findall(r"\{([^{}]+)\}", "{" + suffix)
    if re.sub(r"\{[^{}]+\}", "", "{" + suffix).strip() or len(groups) > 5:
        raise ValueError("Usa restricciones como { -2 < x < 2 }.")
    restrictions = []
    for group in groups:
        for chain in _parts(group):
            tokens = RELATION.split(chain)
            if len(tokens) not in (3, 5):
                raise ValueError("Cada restricción debe incluir una desigualdad.")
            for index in range(1, len(tokens), 2):
                operator = tokens[index]
                if operator not in COMPARISONS:
                    raise ValueError("Usa <, >, <= o >= en la restricción.")
                restrictions.append(
                    (_formula(tokens[index - 1]), operator, _formula(tokens[index + 1]))
                )
    if len(restrictions) > 10:
        raise ValueError("Se admiten hasta diez desigualdades de restricción.")
    return base.strip(), restrictions


class _Row:
    def __init__(
        self,
        text: str,
        index: int,
        parameters: Mapping[str, float],
        points: Mapping[str, Point],
        x_range: Range,
        y_range: Range,
        t_range: Range,
        view: str,
    ) -> None:
        self.text = text
        self.index = index
        self.parameters = parameters
        self.points = points
        self.x_range = x_range
        self.y_range = y_range
        self.t_range = t_range
        self.view = view
        self.color = PALETTE[index % len(PALETTE)]
        self.symbols: set[str] = set()
        self.details: str | None = None
        self.explicit_formula: Formula | None = None

    def _variables(
        self, formula: Formula, coordinates: Mapping[sp.Symbol, Array | float]
    ) -> dict[sp.Symbol, Array | float]:
        variables = dict(coordinates)
        for symbol in formula.symbols - coordinates.keys():
            if symbol in AXES:
                raise ValueError(
                    f"La variable {symbol} no está disponible en esta expresión."
                )
            self.symbols.add(symbol.name)
            value = self.parameters.get(symbol.name, 1.0)
            if not math.isfinite(value):
                raise ValueError(f"El parámetro {symbol} debe ser finito.")
            variables[symbol] = value
        return variables

    def _evaluate(
        self,
        formula: Formula,
        coordinates: Mapping[sp.Symbol, Array | float],
        shape: tuple[int, ...],
    ) -> Array:
        return _numeric(formula, self._variables(formula, coordinates), shape)

    def _mask(
        self,
        restrictions: Sequence[tuple[Formula, str, Formula]],
        coordinates: Mapping[sp.Symbol, Array | float],
        shape: tuple[int, ...],
    ) -> NDArray[np.bool_]:
        allowed = np.ones(shape, dtype=bool)
        for left, operator, right in restrictions:
            first = self._evaluate(left, coordinates, shape)
            second = self._evaluate(right, coordinates, shape)
            allowed &= (
                np.isfinite(first)
                & np.isfinite(second)
                & COMPARISONS[operator](first, second)
            )
        return allowed

    def _scalar(self, source: str) -> float:
        value = float(self._evaluate(_formula(source), {}, ()).item())
        if not math.isfinite(value) or abs(value) > MAX_COORDINATE:
            raise ValueError("Usa una coordenada real y finita de magnitud ≤10¹⁰⁰.")
        return value

    def _trace(
        self,
        coordinates: Sequence[Sequence[float] | Array],
        mode: str = "lines",
        **attributes: Any,
    ) -> Trace:
        arrays = [np.asarray(values, dtype=float) for values in coordinates]
        if not np.any(np.logical_and.reduce([np.isfinite(array) for array in arrays])):
            raise ValueError("No hay puntos reales en los intervalos visibles.")
        series = {axis: _json_values(values) for axis, values in zip("xyz", arrays)}
        trace: Trace = {
            **series,
            "type": "scatter3d" if len(coordinates) == 3 else "scatter",
            "mode": mode,
            "name": self.text,
            "legendgroup": str(self.index),
            "connectgaps": False,
            **attributes,
        }
        if "lines" in mode:
            trace["line"] = {"color": self.color, "width": 2.5}
        if "markers" in mode:
            trace["marker"] = {"color": self.color, "size": 7}
        return trace

    def _curve(
        self,
        formula: Formula,
        restrictions: Sequence[tuple[Formula, str, Formula]],
        dependent: sp.Symbol = Y,
    ) -> Trace:
        independent = Y if dependent == X else X
        limits = self.y_range if independent == Y else self.x_range
        samples = np.linspace(*limits, 601)
        coordinates = {independent: samples}
        values = self._evaluate(formula, coordinates, samples.shape)
        # Trigonometric poles have no explicit division node.
        midpoints = (samples[:-1] + samples[1:]) / 2
        middle = self._evaluate(formula, {independent: midpoints}, midpoints.shape)
        with np.errstate(all="ignore"):
            scale = (
                (self.x_range[1] - self.x_range[0])
                if dependent == X
                else (self.y_range[1] - self.y_range[0])
            )
            discontinuity = (np.abs(values[1:] - values[:-1]) > scale) & (
                (middle < np.minimum(values[:-1], values[1:]))
                | (middle > np.maximum(values[:-1], values[1:]))
            )
        values[1:][discontinuity] = np.nan
        coordinates[dependent] = values
        values[~self._mask(restrictions, coordinates, samples.shape)] = np.nan
        return self._trace((coordinates[X], coordinates[Y]))

    def _parametric(
        self,
        formulas: Sequence[Formula],
        restrictions: Sequence[tuple[Formula, str, Formula]],
        *,
        polar: bool = False,
    ) -> Trace:
        expected = 3 if self.view == "3d" else 2
        if not polar and len(formulas) != expected:
            raise ValueError(f"Esta vista requiere {expected} coordenadas.")
        if polar and self.view != "2d":
            raise ValueError("Las curvas polares pertenecen a la vista 2D.")
        if not polar and not any(T in item.symbols for item in formulas):
            coordinates = tuple(
                np.asarray([float(self._evaluate(item, {}, ()).item())])
                for item in formulas
            )
            point_coordinates = dict(zip((X, Y, Z), coordinates))
            if not self._mask(restrictions, point_coordinates, (1,)).item():
                raise ValueError("El punto queda fuera de la restricción.")
            return self._trace(coordinates, "markers")
        t = np.linspace(*self.t_range, 601)
        values = tuple(self._evaluate(item, {T: t}, t.shape) for item in formulas)
        coordinates = (
            (values[0] * np.cos(t), values[0] * np.sin(t)) if polar else values
        )
        variables = dict(zip((X, Y, Z), coordinates))
        variables[T] = t
        if polar:
            variables[R] = values[0]
        allowed = self._mask(restrictions, variables, t.shape)
        return self._trace(
            tuple(np.where(allowed, value, np.nan) for value in coordinates)
        )

    def _grid(self, count: int) -> tuple[Array, Array, Array, Array]:
        xs, ys = np.linspace(*self.x_range, count), np.linspace(*self.y_range, count)
        x, y = np.meshgrid(xs, ys)
        return xs, ys, x, y

    def _surface(
        self, formula: Formula, restrictions: Sequence[tuple[Formula, str, Formula]]
    ) -> Trace:
        xs, ys, x, y = self._grid(65)
        z = self._evaluate(formula, {X: x, Y: y}, x.shape)
        z[~self._mask(restrictions, {X: x, Y: y, Z: z}, x.shape)] = np.nan
        if not np.isfinite(z).any():
            raise ValueError("No hay una superficie real en los intervalos visibles.")
        return {
            "type": "surface",
            "x": xs.tolist(),
            "y": ys.tolist(),
            "z": _json_values(z),
            "name": self.text,
            "legendgroup": str(self.index),
            "colorscale": [[0, "#edf3ee"], [1, self.color]],
            "showscale": False,
            "showlegend": True,
            "connectgaps": False,
        }

    def _relation(
        self,
        left: Formula,
        right: Formula,
        operator: str,
        restrictions: Sequence[tuple[Formula, str, Formula]],
    ) -> list[Trace]:
        xs, ys, x, y = self._grid(151)
        coordinates = {X: x, Y: y}
        with np.errstate(all="ignore"):
            z = self._evaluate(left, coordinates, x.shape) - self._evaluate(
                right, coordinates, x.shape
            )
        if operator == "=":
            difference = left.value - right.value
            residual = _zero_set(difference)
            if residual != difference:
                signed = self._evaluate(Formula(residual), coordinates, x.shape)
                z = np.where(np.isfinite(z), signed, np.nan)
        z[~self._mask(restrictions, coordinates, x.shape)] = np.nan
        finite = np.isfinite(z)
        if not finite.any():
            raise ValueError("No hay muestras reales en los intervalos visibles.")
        minimum, maximum = float(z[finite].min()), float(z[finite].max())
        crosses_zero = minimum < 0 < maximum
        payload = {
            "type": "contour",
            "x": xs.tolist(),
            "y": ys.tolist(),
            "z": _json_values(z),
            "name": self.text,
            "legendgroup": str(self.index),
            "showscale": False,
            "connectgaps": False,
            "hoverinfo": "skip",
        }
        line: dict[str, Any] = {"color": self.color, "width": 2.3}
        if operator in {"<", ">"}:
            line["dash"] = "dash"
        boundary = {
            **payload,
            "showlegend": True,
            "autocontour": False,
            "contours": {"start": 0, "end": 0, "size": 1, "coloring": "none"},
            "line": line,
        }
        if operator == "=":
            if not crosses_zero:
                zeros = finite & (z == 0)
                if (z[finite] == 0).all():
                    self.details = (
                        "La igualdad se cumple en toda la zona válida muestreada."
                    )
                    return []
                if zeros.any():
                    return [self._trace((x[zeros], y[zeros]), "markers")]
                self.details = "Sin soluciones detectadas en la zona muestreada."
                return []
            return [boundary]
        region = {
            **payload,
            "showlegend": False,
            "opacity": 0.18,
            "contours": {
                "type": "constraint",
                "operation": operator,
                "value": 0,
                "showlines": False,
            },
            "fillcolor": self.color,
            "line": {"width": 0},
        }
        if crosses_zero:
            self.details = (
                "Frontera discontinua (estricta) · Región sombreada"
                if operator in {"<", ">"}
                else "Frontera continua (inclusiva) · Región sombreada"
            )
            return [region, boundary]
        satisfied = COMPARISONS[operator](z[finite], 0)
        if not satisfied.any():
            self.details = "Sin región detectada en la zona muestreada."
            return []
        region["showlegend"] = True
        self.details = (
            "Frontera discontinua (estricta) · Región sombreada"
            if operator in {"<", ">"}
            else "Frontera continua (inclusiva) · Región sombreada"
        )
        return [region]

    def _point(self, source: str) -> Point:
        if source in self.points:
            return self.points[source]
        if re.fullmatch(r"[A-Z]", source):
            raise ValueError(f"Define el punto {source} con {source}=(x,y).")
        if not source.startswith("(") or not source.endswith(")"):
            raise ValueError("Cada punto debe escribirse como (x,y).")
        parts = _parts(source[1:-1])
        if len(parts) not in (2, 3):
            raise ValueError("Un punto debe tener dos o tres coordenadas.")
        return tuple(self._scalar(part) for part in parts)

    def _point_trace(self, point: Point, label: str | None = None) -> Trace:
        expected = 3 if self.view == "3d" else 2
        if len(point) != expected:
            raise ValueError(f"Esta vista requiere puntos de {expected} coordenadas.")
        if label is None:
            return self._trace(tuple([coordinate] for coordinate in point), "markers")
        return self._trace(
            tuple([coordinate] for coordinate in point),
            "markers+text",
            text=[label],
            textposition="top right",
        )

    def _points_2d(self, parts: Sequence[str]) -> list[tuple[float, float]]:
        points = [self._point(part) for part in parts]
        if any(len(point) != 2 for point in points):
            raise ValueError("Esta construcción requiere puntos 2D.")
        return [(point[0], point[1]) for point in points]

    def _fit(self, points: Sequence[tuple[float, float]], degree: int) -> list[Trace]:
        x, y = (np.asarray(column) for column in zip(*points))
        if len(np.unique(x)) <= degree:
            raise ValueError(
                f"Se requieren al menos {degree + 1} valores distintos de x."
            )
        if np.max(np.abs(x)) > MAX_RANGE or np.max(np.abs(y)) > MAX_RANGE:
            raise ValueError("La regresión admite coordenadas dentro de ±10⁹.")
        polynomial = np.polynomial.Polynomial.fit(x, y, degree)
        sample = np.linspace(*self.x_range, 301)
        residual = np.sum((y - polynomial(x)) ** 2)
        total = np.sum((y - y.mean()) ** 2)
        coefficients = polynomial.convert().coef
        terms = [f"{coefficients[0]:.6g}"]
        terms.extend(
            f"{coefficient:+.6g}x" + (f"^{power}" if power > 1 else "")
            for power, coefficient in enumerate(coefficients[1:], start=1)
        )
        self.details = "y = " + " ".join(terms)
        if total > 0:
            self.details += f" · R² = {1 - residual / total:.6g}"
        return [
            self._trace((x, y), "markers", name="Datos observados"),
            self._trace((sample, polynomial(sample)), name=f"Ajuste de grado {degree}"),
        ]

    def _construction(self, command: str, parts: list[str]) -> list[Trace]:
        if self.view != "2d":
            raise ValueError("Esta construcción pertenece a la vista 2D.")
        if command in {"table", "fit", "polygon"}:
            if len(parts) > MAX_POINTS:
                raise ValueError(f"Se admiten hasta {MAX_POINTS} puntos por fila.")
            if command == "fit":
                degree = 1
                if parts[0] in {"1", "2", "3"}:
                    degree = int(parts.pop(0))
                if len(parts) <= degree:
                    raise ValueError(f"Se requieren al menos {degree + 1} puntos.")
                return self._fit(self._points_2d(parts), degree)
            points = self._points_2d(parts)
            if command == "table":
                return [self._trace(tuple(zip(*points)), "markers", name="Datos")]
            if len(points) < 3:
                raise ValueError("El polígono requiere al menos tres puntos.")
            return [
                self._trace(
                    tuple(zip(*points, points[0])),
                    "lines+markers",
                    fill="toself",
                    opacity=0.8,
                )
            ]

        if command == "intersection":
            if len(parts) != 4:
                raise ValueError("Usa intersection(A,B,C,D) para dos rectas.")
            a, b, c, d = self._points_2d(parts)
            ab = np.subtract(b, a)
            cd = np.subtract(d, c)
            denominator = float(ab[0] * cd[1] - ab[1] * cd[0])
            if denominator == 0:
                raise ValueError("Las rectas no tienen una intersección única.")
            ac = np.subtract(c, a)
            factor = (ac[0] * cd[1] - ac[1] * cd[0]) / denominator
            result = np.asarray(a) + factor * ab
            return [self._point_trace((float(result[0]), float(result[1])))]

        if command not in {"segment", "line", "circle", "midpoint", "distance"}:
            raise ValueError(f"Comando desconocido: {command}.")
        if len(parts) != 2:
            raise ValueError(f"{command} requiere dos argumentos.")
        if command == "circle":
            center = self._points_2d(parts[:1])[0]
            radius = self._scalar(parts[1])
            if radius <= 0:
                raise ValueError("El radio debe ser positivo.")
            angle = np.linspace(0, math.tau, 301)
            return [
                self._trace(
                    (
                        center[0] + radius * np.cos(angle),
                        center[1] + radius * np.sin(angle),
                    )
                )
            ]
        a, b = self._points_2d(parts)
        if command == "segment":
            return [self._trace(tuple(zip(a, b)), "lines+markers")]
        if command == "midpoint":
            return [self._point_trace(tuple((p + q) / 2 for p, q in zip(a, b)))]
        if command == "distance":
            self.details = f"Distancia = {math.dist(a, b):.6g}"
            return []
        if a == b:
            raise ValueError("Una recta requiere dos puntos distintos.")
        if a[0] == b[0]:
            return [self._trace(([a[0]] * 2, self.y_range))]
        slope = (b[1] - a[1]) / (b[0] - a[0])
        return [
            self._trace(
                (self.x_range, [a[1] + slope * (x - a[0]) for x in self.x_range])
            )
        ]

    def _symbolic(self, command: str, argument: str) -> Formula:
        formula = _formula(argument)
        self._variables(formula, {X: 0.0})
        if command == "derivative":
            value = sp.diff(formula.value, X)
            self.details = str(value).replace("**", "^")
            return Formula(value, formula.divisors)
        if _degree(formula.value) > 100:
            raise ValueError("El grado de la integral no puede superar 100.")
        integral = sp.Poly(formula.value, X).integrate().as_expr()
        self.details = str(integral).replace("**", "^") + " + C"
        return Formula(integral, formula.divisors)

    def _find_roots_1d(self, formula: Formula, max_count: int = 12) -> list[float]:
        samples = np.linspace(*self.x_range, 601)
        values = self._evaluate(formula, {X: samples}, samples.shape)
        found: list[float] = []
        for i in range(len(samples) - 1):
            y1, y2 = float(values[i]), float(values[i + 1])
            if not (math.isfinite(y1) and math.isfinite(y2)):
                continue
            x1, x2 = float(samples[i]), float(samples[i + 1])
            if abs(y1) < 1e-9:
                cand = round(x1, 6)
                if not any(abs(cand - r) < 1e-3 for r in found):
                    found.append(cand)
            elif y1 * y2 < 0 and abs(y2 - y1) < (self.y_range[1] - self.y_range[0]):
                lo, hi = x1, x2
                f_lo = y1
                for _ in range(18):
                    mid = 0.5 * (lo + hi)
                    f_mid = float(self._evaluate(formula, {X: mid}, ()).item())
                    if not math.isfinite(f_mid):
                        break
                    if abs(f_mid) < 1e-10:
                        lo = hi = mid
                        break
                    if f_lo * f_mid <= 0:
                        hi = mid
                    else:
                        lo = mid
                        f_lo = f_mid
                root_x = round(0.5 * (lo + hi), 6)
                f_root = float(self._evaluate(formula, {X: root_x}, ()).item())
                if math.isfinite(f_root) and abs(f_root) < 1e-2:
                    if not any(abs(root_x - r) < 1e-3 for r in found):
                        found.append(root_x)
            if len(found) >= max_count:
                break
        return found

    def _calculus_command(
        self,
        name: str,
        parts: list[str],
        restrictions: Sequence[tuple[Formula, str, Formula]],
    ) -> list[Trace]:
        if name == "tangentplane":
            if self.view != "3d":
                raise ValueError("tangentplane requiere la vista 3D.")
            if len(parts) != 3:
                raise ValueError("Usa tangentplane(f(x,y), x0, y0).")
            formula = _formula(parts[0])
            x0, y0 = self._scalar(parts[1]), self._scalar(parts[2])
            z0 = float(self._evaluate(formula, {X: x0, Y: y0}, ()).item())
            if not math.isfinite(z0):
                raise ValueError("La función no está definida en el punto indicado.")
            fx_form = Formula(sp.diff(formula.value, X), formula.divisors)
            fy_form = Formula(sp.diff(formula.value, Y), formula.divisors)
            fx0 = float(self._evaluate(fx_form, {X: x0, Y: y0}, ()).item())
            fy0 = float(self._evaluate(fy_form, {X: x0, Y: y0}, ()).item())
            if not (math.isfinite(fx0) and math.isfinite(fy0)):
                raise ValueError("Las derivadas parciales no son finitas en el punto.")
            plane_expr = sp.simplify(
                sp.Float(round(z0, 6))
                + sp.Float(round(fx0, 6)) * (X - sp.Float(round(x0, 6)))
                + sp.Float(round(fy0, 6)) * (Y - sp.Float(round(y0, 6)))
            )
            self.details = (
                f"z = {str(plane_expr).replace('**', '^')} · "
                f"∇f({x0:g},{y0:g}) = ({fx0:.4g}, {fy0:.4g})"
            )
            surface = self._surface(Formula(plane_expr), restrictions)
            surface["opacity"] = 0.55
            point = self._point_trace((x0, y0, z0), f"P({x0:g},{y0:g},{z0:.3g})")
            return [surface, point]

        if self.view != "2d":
            raise ValueError(f"{name} pertenece a la vista 2D.")

        if name in {"tangent", "normal"}:
            if len(parts) != 2:
                raise ValueError(f"Usa {name}(f(x), x0).")
            formula = _formula(parts[0])
            x0 = self._scalar(parts[1])
            y0 = float(self._evaluate(formula, {X: x0}, ()).item())
            deriv = Formula(sp.diff(formula.value, X), formula.divisors)
            m = float(self._evaluate(deriv, {X: x0}, ()).item())
            if not (math.isfinite(y0) and math.isfinite(m)):
                raise ValueError("La función o su derivada no es finita en x0.")
            if name == "normal":
                if abs(m) < 1e-9:
                    self.details = f"x = {x0:g} (normal vertical en ({x0:g}, {y0:.6g}))"
                    return [
                        self._trace(([x0, x0], self.y_range)),
                        self._point_trace((x0, y0), f"N({x0:g},{y0:.3g})"),
                    ]
                slope = -1.0 / m
                tag = "N"
            else:
                slope = m
                tag = "T"
            line_expr = sp.simplify(
                sp.Float(round(y0, 6))
                + sp.Float(round(slope, 6)) * (X - sp.Float(round(x0, 6)))
            )
            self.details = (
                f"y = {str(line_expr).replace('**', '^')} · "
                f"m = {slope:.6g} en ({x0:g}, {y0:.6g})"
            )
            xs = [self.x_range[0], self.x_range[1]]
            ys = [y0 + slope * (x_val - x0) for x_val in xs]
            line_trace = self._trace(
                (xs, ys), line={"color": self.color, "width": 2.2, "dash": "dot"}
            )
            pt_trace = self._point_trace((x0, y0), f"{tag}({x0:g},{y0:.3g})")
            return [line_trace, pt_trace]

        if name == "integral":
            if len(parts) == 1:
                return [self._curve(self._symbolic("integral", parts[0]), restrictions)]
            if len(parts) != 3:
                raise ValueError("Usa integral(f(x)) o integral(f(x), a, b).")
            formula = _formula(parts[0])
            a, b = self._scalar(parts[1]), self._scalar(parts[2])
            low, high = (a, b) if a <= b else (b, a)
            sign = 1.0 if a <= b else -1.0
            samples = np.linspace(low, high, 241)
            values = self._evaluate(formula, {X: samples}, samples.shape)
            finite_mask = np.isfinite(values)
            if not finite_mask.any():
                raise ValueError("La función no es integrable en el intervalo dado.")
            area_num = sign * float(
                np.trapezoid(values[finite_mask], samples[finite_mask])
            )
            self.details = f"∫[{a:g}, {b:g}] ≈ {area_num:.6g}"
            area_trace = self._trace(
                (samples, values),
                fill="tozeroy",
                fillcolor="rgba(33, 102, 83, 0.22)",
                name=f"Área ∫[{a:g},{b:g}]",
            )
            return [area_trace]

        if name == "riemann":
            if len(parts) not in (4, 5):
                raise ValueError(
                    "Usa riemann(f(x), a, b, n) o riemann(f(x), a, b, n, metodo)."
                )
            formula = _formula(parts[0])
            a, b = self._scalar(parts[1]), self._scalar(parts[2])
            n = int(round(self._scalar(parts[3])))
            if not 1 <= n <= 100:
                raise ValueError("El número de particiones n debe estar entre 1 y 100.")
            method = parts[4].strip().lower() if len(parts) == 5 else "midpoint"
            if method not in {"left", "right", "midpoint", "trapezoid"}:
                raise ValueError(
                    "Método inválido: usa left, right, midpoint o trapezoid."
                )
            low, high = (a, b) if a <= b else (b, a)
            sign = 1.0 if a <= b else -1.0
            edges = np.linspace(low, high, n + 1)
            dx = (high - low) / n if n > 0 else 0.0
            poly_x: list[float] = []
            poly_y: list[float] = []
            total = 0.0
            for i in range(n):
                xl, xr = float(edges[i]), float(edges[i + 1])
                if method == "left":
                    h = float(self._evaluate(formula, {X: xl}, ()).item())
                    if not math.isfinite(h):
                        continue
                    total += h * dx
                    poly_x.extend([xl, xl, xr, xr, xl, float("nan")])
                    poly_y.extend([0.0, h, h, 0.0, 0.0, float("nan")])
                elif method == "right":
                    h = float(self._evaluate(formula, {X: xr}, ()).item())
                    if not math.isfinite(h):
                        continue
                    total += h * dx
                    poly_x.extend([xl, xl, xr, xr, xl, float("nan")])
                    poly_y.extend([0.0, h, h, 0.0, 0.0, float("nan")])
                elif method == "trapezoid":
                    yl = float(self._evaluate(formula, {X: xl}, ()).item())
                    yr = float(self._evaluate(formula, {X: xr}, ()).item())
                    if not (math.isfinite(yl) and math.isfinite(yr)):
                        continue
                    total += 0.5 * (yl + yr) * dx
                    poly_x.extend([xl, xl, xr, xr, xl, float("nan")])
                    poly_y.extend([0.0, yl, yr, 0.0, 0.0, float("nan")])
                else:
                    xm = 0.5 * (xl + xr)
                    h = float(self._evaluate(formula, {X: xm}, ()).item())
                    if not math.isfinite(h):
                        continue
                    total += h * dx
                    poly_x.extend([xl, xl, xr, xr, xl, float("nan")])
                    poly_y.extend([0.0, h, h, 0.0, 0.0, float("nan")])
            if not poly_x:
                raise ValueError("No hay particiones finitas en el intervalo.")
            r_sum = sign * total
            dense_x = np.linspace(low, high, 241)
            dense_y = self._evaluate(formula, {X: dense_x}, dense_x.shape)
            fin = np.isfinite(dense_y)
            exact_num = (
                sign * float(np.trapezoid(dense_y[fin], dense_x[fin]))
                if fin.any()
                else r_sum
            )
            self.details = (
                f"Suma ({method}, n={n}) = {r_sum:.6g} · "
                f"∫ ≈ {exact_num:.6g} · Error = {abs(exact_num - r_sum):.4g}"
            )
            return [
                self._trace(
                    (poly_x, poly_y),
                    fill="toself",
                    fillcolor="rgba(180, 83, 9, 0.22)",
                    name=f"Riemann ({method}, n={n})",
                )
            ]

        if name == "taylor":
            if len(parts) not in (2, 3):
                raise ValueError("Usa taylor(f(x), n) o taylor(f(x), x0, n).")
            formula = _formula(parts[0])
            self._variables(formula, {X: 0.0})
            if len(parts) == 2:
                x0 = 0.0
                deg = int(round(self._scalar(parts[1])))
            else:
                x0 = self._scalar(parts[1])
                deg = int(round(self._scalar(parts[2])))
            if not 1 <= deg <= 12:
                raise ValueError(
                    "El grado del polinomio de Taylor debe estar entre 1 y 12."
                )
            vars_sub = {
                s: self.parameters.get(s.name, 1.0)
                for s in formula.symbols
                if s != X and s not in AXES
            }
            expr_sub = formula.value.subs(vars_sub)
            poly = sp.series(expr_sub, X, x0, deg + 1).removeO()
            self.details = f"T_{deg}(x) = {str(poly).replace('**', '^')}"
            return [self._curve(Formula(poly), restrictions)]

        if name == "roots":
            if len(parts) != 1:
                raise ValueError("Usa roots(f(x)).")
            formula = _formula(parts[0])
            roots = self._find_roots_1d(formula)
            if not roots:
                self.details = "Sin raíces reales en el intervalo visible."
                return []
            self.details = "Raíces: " + ", ".join(f"({r:g}, 0)" for r in roots)
            return [
                self._trace(
                    (roots, [0.0] * len(roots)),
                    "markers+text",
                    text=[f"({r:g}, 0)" for r in roots],
                    textposition="top center",
                    name="Raíces",
                )
            ]

        if name == "extrema":
            if len(parts) != 1:
                raise ValueError("Usa extrema(f(x)).")
            formula = _formula(parts[0])
            d1 = Formula(sp.diff(formula.value, X), formula.divisors)
            d2 = Formula(sp.diff(d1.value, X), formula.divisors)
            crit_xs = self._find_roots_1d(d1)
            xs_ext: list[float] = []
            ys_ext: list[float] = []
            labels: list[str] = []
            for cx in crit_xs:
                cy = float(self._evaluate(formula, {X: cx}, ()).item())
                conc = float(self._evaluate(d2, {X: cx}, ()).item())
                if math.isfinite(cy) and math.isfinite(conc) and abs(conc) > 1e-7:
                    kind = "Mín" if conc > 0 else "Máx"
                    xs_ext.append(cx)
                    ys_ext.append(round(cy, 6))
                    labels.append(f"{kind}({cx:g}, {cy:.4g})")
            if not xs_ext:
                self.details = "Sin extremos locales detectados en el intervalo."
                return []
            self.details = "Extremos: " + ", ".join(labels)
            return [
                self._trace(
                    (xs_ext, ys_ext),
                    "markers+text",
                    text=labels,
                    textposition="top center",
                    name="Extremos locales",
                )
            ]

        if name == "intersect":
            if len(parts) != 2:
                raise ValueError("Usa intersect(f(x), g(x)).")
            f1, f2 = _formula(parts[0]), _formula(parts[1])
            diff = Formula(f1.value - f2.value, f1.divisors + f2.divisors)
            ixs = self._find_roots_1d(diff)
            pts_x: list[float] = []
            pts_y: list[float] = []
            labels_i: list[str] = []
            for ix in ixs:
                iy = float(self._evaluate(f1, {X: ix}, ()).item())
                if math.isfinite(iy):
                    pts_x.append(ix)
                    pts_y.append(round(iy, 6))
                    labels_i.append(f"({ix:g}, {iy:.4g})")
            if not pts_x:
                self.details = "Sin intersecciones reales en el intervalo visible."
                return []
            self.details = "Intersecciones: " + ", ".join(labels_i)
            return [
                self._trace(
                    (pts_x, pts_y),
                    "markers+text",
                    text=labels_i,
                    textposition="top center",
                    name="Intersecciones",
                )
            ]

        if name == "contour":
            if len(parts) != 1:
                raise ValueError("Usa contour(f(x,y)).")
            formula = _formula(parts[0])
            grid_x, grid_y, x, y = self._grid(101)
            z = self._evaluate(formula, {X: x, Y: y}, x.shape)
            z[~self._mask(restrictions, {X: x, Y: y}, x.shape)] = np.nan
            if not np.isfinite(z).any():
                raise ValueError("No hay muestras reales para las curvas de nivel.")
            self.details = f"Mapa de curvas de nivel de {parts[0]}"
            return [
                {
                    "type": "contour",
                    "x": grid_x.tolist(),
                    "y": grid_y.tolist(),
                    "z": _json_values(z),
                    "name": self.text,
                    "legendgroup": str(self.index),
                    "colorscale": "YlGnBu",
                    "contours": {"coloring": "lines", "showlabels": True},
                    "showscale": False,
                    "connectgaps": False,
                }
            ]

        if name == "gradient":
            if len(parts) != 3:
                raise ValueError("Usa gradient(f(x,y), x0, y0).")
            formula = _formula(parts[0])
            x0, y0 = self._scalar(parts[1]), self._scalar(parts[2])
            fx = Formula(sp.diff(formula.value, X), formula.divisors)
            fy = Formula(sp.diff(formula.value, Y), formula.divisors)
            gx = float(self._evaluate(fx, {X: x0, Y: y0}, ()).item())
            gy = float(self._evaluate(fy, {X: x0, Y: y0}, ()).item())
            if not (math.isfinite(gx) and math.isfinite(gy)):
                raise ValueError("El gradiente no es finito en el punto indicado.")
            norm = math.hypot(gx, gy)
            self.details = (
                f"∇f({x0:g}, {y0:g}) = ({gx:.6g}, {gy:.6g}) · |∇f| = {norm:.6g}"
            )
            scale = (
                0.15 * (self.x_range[1] - self.x_range[0]) / norm
                if norm > 1e-9
                else 0.0
            )
            return [
                self._trace(
                    ([x0, x0 + gx * scale], [y0, y0 + gy * scale]),
                    "lines+markers",
                    name=f"∇f({x0:g},{y0:g})",
                )
            ]

        raise ValueError(f"Comando desconocido: {name}.")

    def traces(self) -> list[Trace]:
        text = (
            self.text.replace("≤", "<=")
            .replace("≥", ">=")
            .replace("−", "-")
            .replace("θ", "t")
            .replace("Θ", "t")
        )
        base, restrictions = _conditions(text)
        named = NAMED_POINT.fullmatch(base)
        if named:
            if restrictions:
                raise ValueError(
                    "Las construcciones con nombre no admiten restricciones."
                )
            name, coordinates = named.groups()
            return [self._point_trace(self._point(coordinates), name)]
        command = COMMAND.fullmatch(base)
        if command:
            name, arguments = command.groups()
            if name == "derivative" and self.view == "2d":
                return [self._curve(self._symbolic(name, arguments), restrictions)]
            if name in {
                "integral",
                "tangent",
                "normal",
                "riemann",
                "taylor",
                "roots",
                "extrema",
                "intersect",
                "contour",
                "gradient",
                "tangentplane",
            }:
                return self._calculus_command(name, _parts(arguments), restrictions)
            if name in {
                "segment",
                "line",
                "circle",
                "polygon",
                "midpoint",
                "distance",
                "intersection",
                "table",
                "fit",
            }:
                if restrictions:
                    raise ValueError("Las construcciones no admiten restricciones.")
                return self._construction(name, _parts(arguments))
        parts = _tuple_parts(base)
        if len(parts) > 1:
            return [self._parametric([_formula(part) for part in parts], restrictions)]

        tokens = RELATION.split(base)
        if len(tokens) == 1:
            expression = _formula(base)
            if self.view == "3d":
                return [self._surface(expression, restrictions)]
            if not restrictions and not (expression.symbols & {Y, Z, T, R}):
                self.explicit_formula = expression
            return [self._curve(expression, restrictions)]
        if len(tokens) != 3:
            raise ValueError(
                "Escribe una relación por fila y añade límites entre llaves."
            )
        lhs, operator, rhs = (token.strip() for token in tokens)
        left, right = _formula(lhs), _formula(rhs)
        if self.view == "3d":
            if operator == "=" and lhs == "z" and Z not in right.symbols:
                return [self._surface(right, restrictions)]
            if operator == "=" and rhs == "z" and Z not in left.symbols:
                return [self._surface(left, restrictions)]
            raise ValueError("En 3D escribe z=f(x,y) o una curva (x(t),y(t),z(t)).")
        if operator == "=":
            for name, formula in ((lhs, right), (rhs, left)):
                if name == "r" and R not in formula.symbols:
                    return [self._parametric([formula], restrictions, polar=True)]
                if name == "y" and Y not in formula.symbols:
                    if not restrictions:
                        self.explicit_formula = formula
                    return [self._curve(formula, restrictions)]
                if name == "x" and X not in formula.symbols:
                    return [self._curve(formula, restrictions, dependent=X)]
        return self._relation(left, right, operator, restrictions)


def build_graph(
    expressions: Sequence[str],
    parameters: Mapping[str, float] | None = None,
    *,
    x_range: Range = (-10.0, 10.0),
    y_range: Range = (-10.0, 10.0),
    t_range: Range = (0.0, math.tau),
    view: str = "2d",
    hidden_rows: Collection[int] = (),
) -> GraphResult:
    """Sample a worksheet and report recoverable failures by source row."""
    x_range, y_range, t_range = _range(x_range), _range(y_range), _range(t_range)
    if view not in {"2d", "3d"}:
        raise ValueError("La vista debe ser 2d o 3d.")
    if len(expressions) > MAX_ROWS:
        raise ValueError(f"Se admiten hasta {MAX_ROWS} filas.")
    result = GraphResult()
    parameter_names: set[str] = set()
    points: dict[str, Point] = {}
    rows = [
        _Row(
            text.strip(),
            index,
            parameters or {},
            points,
            x_range,
            y_range,
            t_range,
            view,
        )
        for index, text in enumerate(expressions)
        if text.strip()
    ]
    failures = (ValueError, ArithmeticError, TypeError, KeyError, StructuredMathError)
    for row in rows:
        if len(row.text) > 12000:
            if row.index not in hidden_rows:
                result.errors[row.index] = (
                    "La fila supera la longitud máxima permitida."
                )
            continue
        named = NAMED_POINT.fullmatch(row.text)
        if named:
            name, coordinates = named.groups()
            try:
                if name in points:
                    raise ValueError(f"El punto {name} ya está definido en otra fila.")
                point = row._point(coordinates)
                if len(point) != (3 if view == "3d" else 2):
                    raise ValueError(
                        "El punto no coincide con la dimensión de esta vista."
                    )
                points[name] = point
            except failures as error:
                if row.index not in hidden_rows:
                    result.errors[row.index] = _error_text(error)

    explicit_rows: list[_Row] = []
    for row in rows:
        if row.index not in result.errors and row.index not in hidden_rows:
            try:
                result.traces.extend(row.traces())
                if row.details:
                    result.details[row.index] = row.details
                if row.explicit_formula is not None:
                    explicit_rows.append(row)
            except failures as error:
                result.errors[row.index] = _error_text(error)
        parameter_names.update(row.symbols)
    result.parameters = tuple(sorted(parameter_names))
    if view == "2d" and explicit_rows:
        result.notable_points = _compute_notable_points(explicit_rows, x_range)
    return result


def _compute_notable_points(
    explicit_rows: Sequence[_Row], x_range: Range
) -> list[dict[str, Any]]:
    """Detecta raíces, corte Y, extremos locales e intersecciones estilo Desmos."""
    notable: list[dict[str, Any]] = []
    primary = explicit_rows[0]
    formula = primary.explicit_formula
    if formula is None:
        return notable
    try:
        if x_range[0] <= 0.0 <= x_range[1]:
            y0 = float(primary._evaluate(formula, {X: 0.0}, ()).item())
            if math.isfinite(y0):
                notable.append(
                    {
                        "kind": "y_intercept",
                        "label": f"Corte Y (0, {round(y0, 4):g})",
                        "x": 0.0,
                        "y": round(y0, 4),
                        "series": primary.text,
                    }
                )
        for rx in primary._find_roots_1d(formula, max_count=6):
            notable.append(
                {
                    "kind": "root",
                    "label": f"Raíz ({round(rx, 4):g}, 0)",
                    "x": round(rx, 4),
                    "y": 0.0,
                    "series": primary.text,
                }
            )
        d1 = Formula(sp.diff(formula.value, X), formula.divisors)
        d2 = Formula(sp.diff(d1.value, X), formula.divisors)
        for cx in primary._find_roots_1d(d1, max_count=6):
            cy = float(primary._evaluate(formula, {X: cx}, ()).item())
            conc = float(primary._evaluate(d2, {X: cx}, ()).item())
            if math.isfinite(cy) and math.isfinite(conc) and abs(conc) > 1e-6:
                is_min = conc > 0
                kind_lbl = "Mín. local" if is_min else "Máx. local"
                notable.append(
                    {
                        "kind": "local_min" if is_min else "local_max",
                        "label": f"{kind_lbl} ({round(cx, 4):g}, {round(cy, 4):g})",
                        "x": round(cx, 4),
                        "y": round(cy, 4),
                        "series": primary.text,
                    }
                )
        if len(explicit_rows) >= 2 and explicit_rows[1].explicit_formula is not None:
            f2 = explicit_rows[1].explicit_formula
            diff = Formula(formula.value - f2.value, formula.divisors + f2.divisors)
            for ix in primary._find_roots_1d(diff, max_count=6):
                iy = float(primary._evaluate(formula, {X: ix}, ()).item())
                if math.isfinite(iy):
                    rx_i, ry_i = round(ix, 4), round(iy, 4)
                    notable.append(
                        {
                            "kind": "intersection",
                            "label": f"Intersección ({rx_i:g}, {ry_i:g})",
                            "x": rx_i,
                            "y": ry_i,
                            "series": f"{primary.text} ∩ {explicit_rows[1].text}",
                        }
                    )
    except Exception:
        pass
    return notable


def evaluate_function_table(
    expressions: Sequence[str],
    parameters: Mapping[str, float] | None = None,
    *,
    x_start: float = -5.0,
    x_end: float = 5.0,
    step: float = 1.0,
    hidden_rows: Collection[int] = (),
) -> tuple[list[str], list[list[str]]]:
    """Genera una tabla (x, f1(x), f2(x), ...) para funciones explícitas."""
    if step <= 0 or not math.isfinite(step):
        step = 1.0
    low, high = (x_start, x_end) if x_start <= x_end else (x_end, x_start)
    count = int(min(50, max(2, round((high - low) / step) + 1)))
    xs = np.linspace(low, low + step * (count - 1), count)

    active_formulas: list[tuple[str, _Row, Formula]] = []
    points: dict[str, Point] = {}
    for index, raw in enumerate(expressions):
        if index in hidden_rows or not raw.strip():
            continue
        row = _Row(
            raw.strip(),
            index,
            parameters or {},
            points,
            (low, high if high > low else low + 1.0),
            (-10.0, 10.0),
            (0.0, math.tau),
            "2d",
        )
        try:
            row.traces()
        except Exception:
            continue
        if row.explicit_formula is not None:
            active_formulas.append((raw.strip(), row, row.explicit_formula))

    headers = ["x"] + [label for label, _, _ in active_formulas]
    if not active_formulas:
        return headers, [[f"{round(float(xv), 4):g}"] for xv in xs]

    evaluated_cols = [
        row._evaluate(form, {X: xs}, xs.shape) for _, row, form in active_formulas
    ]
    table_rows: list[list[str]] = []
    for r_idx, xv in enumerate(xs):
        row_cells = [f"{round(float(xv), 4):g}"]
        for col in evaluated_cols:
            yv = float(col[r_idx])
            row_cells.append(f"{round(yv, 5):g}" if math.isfinite(yv) else "Indefinido")
        table_rows.append(row_cells)
    return headers, table_rows


def _error_text(error: Exception) -> str:
    if isinstance(error, StructuredMathError):
        return error.message
    if isinstance(error, ValueError) and str(error):
        return str(error)
    return "La expresión no se pudo evaluar en esta vista."
