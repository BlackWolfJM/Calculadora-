"""
Motor del Estudio Gráfico Definitivo (Síntesis GeoGebra + Desmos).

Combina:
- De Desmos: lista multi-expresión con colores accesibles, detección automática de
  parámetros libres para sliders, puntos notables (raíces, corte eje Y, extremos
  locales e intersecciones) y generación de tabla de valores.
- De GeoGebra: herramientas geométricas y de cálculo simbólico (recta tangente y
  normal en x0, área de integral definida con sumas de Riemann/trapecios,
  superposición de derivada f'(x), polinomio de Taylor Tn(x, x0) y exploración
  multivariable en 2D Contorno y 3D Superficie z = f(x, y) con plano tangente y
  vector gradiente).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import sympy as sp

from src.domain.modules.derivatives.steps import DerivativeStepGenerator
from src.domain.modules.multivariable.operations import (
    solve_gradient,
    solve_laplacian,
    solve_multivariable_value,
)
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter

# Paleta accesible inspirada en Okabe-Ito + Verde Académico
SERIES_PALETTE: tuple[str, ...] = (
    "#216653",  # Verde esmeralda primario
    "#D55E00",  # Bermellón cálido
    "#0072B2",  # Azul cobalto
    "#AA3377",  # Púrpura intenso
    "#E69F00",  # Ámbar dorado
    "#009E73",  # Turquesa
)

RESERVED_CONSTANTS: frozenset[str] = frozenset({"pi", "e", "E", "I", "oo"})


@dataclass(frozen=True)
class FunctionExpressionSpec:
    """Especificación de una expresión en la lista de funciones tipo Desmos."""

    expr_id: str
    expression: str
    label: str = ""
    color: str = SERIES_PALETTE[0]
    visible: bool = True
    line_dash: str = "solid"


@dataclass(frozen=True)
class CalculusOverlayConfig:
    """Configuración de herramientas de análisis y construcción tipo GeoGebra."""

    show_points_of_interest: bool = True
    show_derivative: bool = False
    tangent_enabled: bool = False
    tangent_x0: float = 1.0
    show_normal: bool = False
    integral_enabled: bool = False
    integral_a: float = 0.0
    integral_b: float = 2.0
    riemann_enabled: bool = False
    riemann_rule: str = "midpoint"  # "left" | "right" | "midpoint" | "trapezoid"
    riemann_n: int = 10
    taylor_enabled: bool = False
    taylor_order: int = 3
    taylor_x0: float = 0.0


@dataclass(frozen=True)
class PointOfInterest:
    """Punto notable detectado automáticamente en el dominio."""

    kind: str  # "root" | "y_intercept" | "local_min" | "local_max" | "intersection"
    label: str
    x: float
    y: float
    series_name: str


@dataclass(frozen=True)
class StudioPreset:
    """Ejemplo interactivo preconfigurado para exploración rápida."""

    preset_id: str
    title: str
    description: str
    mode: str  # "2d" | "contour" | "3d"
    expressions: tuple[str, ...]
    sliders: dict[str, float] = field(default_factory=dict)
    x_min: float = -6.0
    x_max: float = 6.0
    calculus: CalculusOverlayConfig = field(default_factory=CalculusOverlayConfig)


@dataclass(frozen=True)
class StudioRequest:
    """Solicitud inmutable de evaluación para el Estudio Gráfico."""

    mode: str = "2d"  # "2d" | "contour" | "3d"
    expressions: tuple[FunctionExpressionSpec, ...] = ()
    sliders: dict[str, float] = field(default_factory=dict)
    x_min: float = -10.0
    x_max: float = 10.0
    y_min: float = -5.0
    y_max: float = 5.0
    point_x0: float = 1.0
    point_y0: float = 1.0
    show_tangent_plane_3d: bool = False
    calculus: CalculusOverlayConfig = field(default_factory=CalculusOverlayConfig)
    table_start: float = -5.0
    table_end: float = 5.0
    table_step: float = 1.0


@dataclass(frozen=True)
class StudioResult:
    """Resultado completo de evaluación gráfica, simbólica y numérica."""

    mode: str
    traces: list[dict[str, Any]]
    layout_hints: dict[str, Any]
    detected_parameters: list[str]
    points_of_interest: list[PointOfInterest]
    primary_latex: str = ""
    derivative_latex: str = ""
    tangent_latex: str = ""
    normal_latex: str = ""
    taylor_latex: str = ""
    integral_exact_latex: str = ""
    integral_numeric: float | None = None
    riemann_numeric: float | None = None
    multivariable_summary: dict[str, str] = field(default_factory=dict)
    table_headers: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    accessible_summary: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


STUDIO_PRESETS: tuple[StudioPreset, ...] = (
    StudioPreset(
        preset_id="cubic_extrema",
        title="Polinomio cúbico y recta tangente (GeoGebra + Desmos)",
        description=(
            "Raíces, extremos locales, recta tangente en x₀=1 y derivada superpuesta."
        ),
        mode="2d",
        expressions=("x^3 - 3*x", "x - 1"),
        x_min=-3.5,
        x_max=3.5,
        calculus=CalculusOverlayConfig(
            show_points_of_interest=True,
            show_derivative=True,
            tangent_enabled=True,
            tangent_x0=1.2,
        ),
    ),
    StudioPreset(
        preset_id="parametric_wave",
        title="Onda parametrizada con sliders (a·sin(b·x) + c)",
        description=(
            "Deslizadores automáticos para amplitud (a), "
            "frecuencia (b) y desplazamiento (c)."
        ),
        mode="2d",
        expressions=("a * sin(b * x) + c", "cos(x)"),
        sliders={"a": 1.5, "b": 1.0, "c": 0.0},
        x_min=-6.28,
        x_max=6.28,
        calculus=CalculusOverlayConfig(
            show_points_of_interest=True,
            taylor_enabled=True,
            taylor_order=5,
            taylor_x0=0.0,
        ),
    ),
    StudioPreset(
        preset_id="riemann_integral",
        title="Integral definida y Sumas de Riemann",
        description=(
            "Área sombreada bajo f(x) = 4 - x² en [0, 2] con particiones de Riemann."
        ),
        mode="2d",
        expressions=("4 - x^2",),
        x_min=-3.0,
        x_max=3.0,
        calculus=CalculusOverlayConfig(
            show_points_of_interest=True,
            integral_enabled=True,
            integral_a=0.0,
            integral_b=2.0,
            riemann_enabled=True,
            riemann_rule="midpoint",
            riemann_n=8,
        ),
    ),
    StudioPreset(
        preset_id="taylor_approx",
        title="Aproximación por Polinomio de Taylor",
        description=(
            "Comparación de sin(x) con su desarrollo de Taylor de grado 5 en x₀=0."
        ),
        mode="2d",
        expressions=("sin(x)",),
        x_min=-5.0,
        x_max=5.0,
        calculus=CalculusOverlayConfig(
            show_points_of_interest=True,
            taylor_enabled=True,
            taylor_order=5,
            taylor_x0=0.0,
        ),
    ),
    StudioPreset(
        preset_id="surface_saddle_3d",
        title="Superficie 3D: Paraboloide hiperbólico z = x² - y²",
        description=(
            "Exploración 3D con plano tangente, gradiente y laplaciano en (x₀, y₀)."
        ),
        mode="3d",
        expressions=("x^2 - y^2",),
        x_min=-3.0,
        x_max=3.0,
    ),
    StudioPreset(
        preset_id="contour_waves_2d",
        title="Mapa de Contorno 2D: Ondas acopladas sin(x)·cos(y)",
        description="Curvas de nivel e inspección vectorial del gradiente ∇f(x₀, y₀).",
        mode="contour",
        expressions=("sin(x) * cos(y)",),
        x_min=-4.0,
        x_max=4.0,
    ),
)


def _normalize_expression_text(raw: str) -> str:
    """Permite entradas tipo 'f(x) = x^2' o 'y = sin(x)' extrayendo el lado derecho."""
    cleaned = raw.strip()
    if "=" in cleaned:
        lhs, rhs = cleaned.split("=", 1)
        lhs_norm = lhs.strip().replace(" ", "")
        if lhs_norm in {
            "y",
            "z",
            "f(x)",
            "g(x)",
            "h(x)",
            "f(x,y)",
            "g(x,y)",
            "f1(x)",
            "f2(x)",
            "f3(x)",
            "f4(x)",
        }:
            return rhs.strip()
    return cleaned


def detect_free_parameters(
    expressions: list[str] | tuple[str, ...],
    mode: str = "2d",
) -> list[str]:
    """
    Detecta símbolos libres en las expresiones que no son variables independientes
    ('x' en 2D, 'x'/'y' en 3D/Contorno), para crear sliders automáticos estilo Desmos.
    """
    parser = MathParser()
    adapter = SympyAdapter()
    axis_vars = {"x"} if mode == "2d" else {"x", "y"}
    found: set[str] = set()

    for raw in expressions:
        text = _normalize_expression_text(raw)
        if not text:
            continue
        try:
            ast_node = parser.parse(text)
            sym_expr = adapter.ast_to_sympy(ast_node)
            for sym in sym_expr.free_symbols:
                name = str(sym)
                if name not in axis_vars and name not in RESERVED_CONSTANTS:
                    found.add(name)
        except Exception:
            continue

    return sorted(found)


def _evaluate_1d_safe(
    expr: sp.Basic,
    var: sp.Symbol,
    samples: np.ndarray,
    *,
    clip_limit: float = 1e4,
) -> list[float | None]:
    """
    Evalúa una expresión simbólica de 1 variable sobre `samples` de forma segura,
    cortando singularidades simbólicas y saltos asintóticos abruptos.
    """
    if expr.free_symbols - {var}:
        return [None] * len(samples)

    try:
        func = sp.lambdify(var, expr, "numpy")
        with np.errstate(all="ignore"):
            raw_vals = func(samples)
            if np.ndim(raw_vals) == 0:
                values = np.full(samples.shape, float(raw_vals), dtype=float)
            else:
                values = np.asarray(raw_vals, dtype=complex)
    except Exception:
        # Fallback punto a punto si numpy falla en alguna función especial
        clean_fallback: list[float | None] = []
        for x_val in samples:
            try:
                val = complex(expr.subs(var, float(x_val)).evalf())
                if (
                    abs(val.imag) < 1e-9
                    and np.isfinite(val.real)
                    and abs(val.real) <= clip_limit
                ):
                    clean_fallback.append(float(val.real))
                else:
                    clean_fallback.append(None)
            except Exception:
                clean_fallback.append(None)
        return clean_fallback

    clean: list[float | None] = []
    for y in values:
        if np.isreal(y):
            real_y = float(np.real(y))
            if np.isfinite(real_y) and abs(real_y) <= clip_limit:
                clean.append(real_y)
            else:
                clean.append(None)
        else:
            clean.append(None)

    # Cortar singularidades simbólicas conocidas
    try:
        singular = sp.singularities(expr, var)
        if isinstance(singular, sp.FiniteSet):
            for point in singular:
                if point.is_real and point.is_finite:
                    idx = int(np.searchsorted(samples, float(point)))
                    if 0 < idx < len(clean):
                        clean[idx - 1 : idx + 1] = [None, None]
    except Exception:
        pass

    # Cortar saltos asintóticos grandes (ej. tan(x), 1/x)
    dx = float(samples[1] - samples[0]) if len(samples) > 1 else 0.05
    jump_threshold = max(40.0, 250.0 * dx)
    for i in range(1, len(clean)):
        prev_y = clean[i - 1]
        curr_y = clean[i]
        if (
            prev_y is not None
            and curr_y is not None
            and (prev_y * curr_y < 0)
            and abs(curr_y - prev_y) > jump_threshold
        ):
            clean[i - 1] = None

    return clean


def _find_zero_crossings(
    expr: sp.Basic,
    var: sp.Symbol,
    xs: np.ndarray,
    ys: list[float | None],
    max_points: int = 12,
) -> list[float]:
    """Encuentra raíces reales en la malla mediante cambio de signo + bisección."""
    roots: list[float] = []
    func = sp.lambdify(var, expr, "numpy")

    def eval_scalar(x_val: float) -> float | None:
        try:
            with np.errstate(all="ignore"):
                val = func(x_val)
            real_v = float(np.real(val))
            if np.isreal(val) and np.isfinite(real_v):
                return real_v
        except Exception:
            pass
        return None

    for i in range(len(xs) - 1):
        y1 = ys[i]
        y2 = ys[i + 1]
        if y1 is None or y2 is None:
            continue
        x1 = float(xs[i])
        x2 = float(xs[i + 1])

        if abs(y1) < 1e-9:
            candidate = round(x1, 6)
            if not any(abs(candidate - r) < 1e-3 for r in roots):
                roots.append(candidate)
        elif y1 * y2 < 0 and abs(y2 - y1) < 50.0:
            a, b = x1, x2
            fa = y1
            for _ in range(18):
                mid = 0.5 * (a + b)
                fm = eval_scalar(mid)
                if fm is None:
                    break
                if abs(fm) < 1e-10:
                    a = b = mid
                    break
                if fa * fm <= 0:
                    b = mid
                else:
                    a = mid
                    fa = fm
            root_x = round(0.5 * (a + b), 6)
            rm = eval_scalar(root_x)
            if rm is not None and abs(rm) < 1e-2:
                if not any(abs(root_x - r) < 1e-3 for r in roots):
                    roots.append(root_x)
        if len(roots) >= max_points:
            break

    return roots


def _compute_points_of_interest(
    parsed_series: list[tuple[FunctionExpressionSpec, sp.Basic, list[float | None]]],
    var: sp.Symbol,
    samples: np.ndarray,
    x_min: float,
    x_max: float,
) -> list[PointOfInterest]:
    """Calcula raíces, corte con eje Y, extremos locales e intersecciones."""
    points: list[PointOfInterest] = []
    if not parsed_series:
        return points

    primary_spec, primary_expr, primary_ys = parsed_series[0]
    series_title = primary_spec.label or "f₁(x)"

    # 1. Corte con el eje Y (x = 0)
    if x_min <= 0.0 <= x_max:
        y0_list = _evaluate_1d_safe(primary_expr, var, np.array([0.0]))
        if y0_list and y0_list[0] is not None:
            y0_val = round(float(y0_list[0]), 4)
            points.append(
                PointOfInterest(
                    kind="y_intercept",
                    label=f"Corte Y (0, {y0_val:g})",
                    x=0.0,
                    y=y0_val,
                    series_name=series_title,
                )
            )

    # 2. Raíces de la función principal f1(x) = 0
    for root_x in _find_zero_crossings(
        primary_expr, var, samples, primary_ys, max_points=8
    ):
        points.append(
            PointOfInterest(
                kind="root",
                label=f"Raíz ({root_x:g}, 0)",
                x=root_x,
                y=0.0,
                series_name=series_title,
            )
        )

    # 3. Extremos locales (f1'(x) = 0 con cambio de signo)
    try:
        deriv_expr = sp.diff(primary_expr, var)
        deriv_ys = _evaluate_1d_safe(deriv_expr, var, samples)
        crit_xs = _find_zero_crossings(deriv_expr, var, samples, deriv_ys, max_points=6)
        second_deriv = sp.diff(deriv_expr, var)
        for cx in crit_xs:
            cy_list = _evaluate_1d_safe(primary_expr, var, np.array([cx]))
            d2_list = _evaluate_1d_safe(second_deriv, var, np.array([cx]))
            if cy_list and cy_list[0] is not None:
                cy = round(float(cy_list[0]), 4)
                d2 = d2_list[0] if d2_list else None
                if d2 is not None and abs(d2) > 1e-6:
                    is_min = d2 > 0
                    kind = "local_min" if is_min else "local_max"
                    kind_label = "Mín. local" if is_min else "Máx. local"
                    points.append(
                        PointOfInterest(
                            kind=kind,
                            label=f"{kind_label} ({cx:g}, {cy:g})",
                            x=round(cx, 4),
                            y=cy,
                            series_name=series_title,
                        )
                    )
    except Exception:
        pass

    # 4. Intersecciones entre f1(x) y f2(x)
    if len(parsed_series) >= 2:
        sec_spec, sec_expr, _ = parsed_series[1]
        diff_expr = sp.simplify(primary_expr - sec_expr)
        if not diff_expr.is_zero:
            diff_ys = _evaluate_1d_safe(diff_expr, var, samples)
            inter_xs = _find_zero_crossings(
                diff_expr, var, samples, diff_ys, max_points=6
            )
            for ix in inter_xs:
                iy_list = _evaluate_1d_safe(primary_expr, var, np.array([ix]))
                if iy_list and iy_list[0] is not None:
                    iy = round(float(iy_list[0]), 4)
                    points.append(
                        PointOfInterest(
                            kind="intersection",
                            label=f"Intersección ({ix:g}, {iy:g})",
                            x=round(ix, 4),
                            y=iy,
                            series_name=f"{series_title} ∩ {sec_spec.label or 'f₂(x)'}",
                        )
                    )

    return points


def _build_riemann_traces_and_sum(
    expr: sp.Basic,
    var: sp.Symbol,
    a: float,
    b: float,
    n: int,
    rule: str,
) -> tuple[list[dict[str, Any]], float | None]:
    """Construye los polígonos de las particiones de Riemann y su suma numérica."""
    if n < 1:
        n = 1
    if n > 80:
        n = 80
    if a == b:
        return [], 0.0

    low, high = (a, b) if a < b else (b, a)
    sign = 1.0 if a <= b else -1.0
    edges = np.linspace(low, high, n + 1)
    dx = (high - low) / n

    poly_x: list[float | None] = []
    poly_y: list[float | None] = []
    total_area = 0.0

    for i in range(n):
        x_left = float(edges[i])
        x_right = float(edges[i + 1])
        if rule == "left":
            sample_pts = np.array([x_left])
        elif rule == "right":
            sample_pts = np.array([x_right])
        elif rule == "trapezoid":
            sample_pts = np.array([x_left, x_right])
        else:  # midpoint
            sample_pts = np.array([0.5 * (x_left + x_right)])

        y_vals = _evaluate_1d_safe(expr, var, sample_pts)
        if any(v is None for v in y_vals):
            continue

        if rule == "trapezoid":
            y_l = float(y_vals[0])  # type: ignore[arg-type]
            y_r = float(y_vals[1])  # type: ignore[arg-type]
            total_area += 0.5 * (y_l + y_r) * dx
            poly_x.extend([x_left, x_left, x_right, x_right, x_left, None])
            poly_y.extend([0.0, y_l, y_r, 0.0, 0.0, None])
        else:
            h = float(y_vals[0])  # type: ignore[arg-type]
            total_area += h * dx
            poly_x.extend([x_left, x_left, x_right, x_right, x_left, None])
            poly_y.extend([0.0, h, h, 0.0, 0.0, None])

    if not poly_x:
        return [], None

    rule_names = {
        "left": "Izquierda",
        "right": "Derecha",
        "midpoint": "Punto medio",
        "trapezoid": "Trapecios",
    }
    r_label = rule_names.get(rule, "Punto medio")
    trace = {
        "x": poly_x,
        "y": poly_y,
        "mode": "lines",
        "fill": "toself",
        "fillcolor": "rgba(230, 159, 0, 0.22)",
        "line": {"color": "#B27800", "width": 1.4},
        "name": f"Suma de Riemann ({r_label}, n={n})",
        "connectgaps": False,
    }
    return [trace], round(sign * total_area, 6)


def _evaluate_3d_or_contour(
    request: StudioRequest,
    parser: MathParser,
    adapter: SympyAdapter,
) -> StudioResult:
    """Evalúa superficies 3D y mapas de contorno 2D z = f(x, y)."""
    warnings: list[str] = []
    active_specs = [
        s for s in request.expressions if s.visible and s.expression.strip()
    ]
    if not active_specs:
        return StudioResult(
            mode=request.mode,
            traces=[],
            layout_hints={},
            detected_parameters=[],
            points_of_interest=[],
            error=(
                "Introduce al menos una expresión en función de x e y "
                "(por ejemplo, x^2 - y^2)."
            ),
        )

    raw_expr = _normalize_expression_text(active_specs[0].expression)
    detected_params = detect_free_parameters(
        [s.expression for s in active_specs], mode="3d"
    )

    try:
        ast_node = parser.parse(raw_expr)
        sym_expr = adapter.ast_to_sympy(ast_node)
    except Exception as exc:
        return StudioResult(
            mode=request.mode,
            traces=[],
            layout_hints={},
            detected_parameters=detected_params,
            points_of_interest=[],
            error=f"No se pudo interpretar la expresión multivariable: {exc}",
        )

    # Sustituir sliders activos
    subs_map: dict[sp.Symbol, float] = {}
    for sym in list(sym_expr.free_symbols):
        sname = str(sym)
        if sname not in {"x", "y"} and sname not in RESERVED_CONSTANTS:
            subs_map[sym] = float(request.sliders.get(sname, 1.0))
    if subs_map:
        sym_expr = sym_expr.subs(subs_map)

    x_sym = sp.Symbol("x", real=True)
    y_sym = sp.Symbol("y", real=True)

    # Asegurar que los símbolos x, y de la expresión coincidan con x_sym, y_sym
    sym_align = {
        s: (x_sym if str(s) == "x" else y_sym)
        for s in sym_expr.free_symbols
        if str(s) in {"x", "y"}
    }
    sym_expr = sym_expr.subs(sym_align)

    grid_n = 45
    x_min = min(request.x_min, request.x_max - 0.5)
    x_max = max(request.x_max, x_min + 0.5)
    y_min = min(request.y_min, request.y_max - 0.5)
    y_max = max(request.y_max, y_min + 0.5)

    xs = np.linspace(x_min, x_max, grid_n)
    ys = np.linspace(y_min, y_max, grid_n)
    xx, yy = np.meshgrid(xs, ys)

    try:
        func_xy = sp.lambdify((x_sym, y_sym), sym_expr, "numpy")
        with np.errstate(all="ignore"):
            raw_zz = func_xy(xx, yy)
            if np.ndim(raw_zz) == 0:
                zz = np.full(xx.shape, float(raw_zz), dtype=float)
            else:
                zz = np.asarray(raw_zz, dtype=float)
    except Exception as exc:
        return StudioResult(
            mode=request.mode,
            traces=[],
            layout_hints={},
            detected_parameters=detected_params,
            points_of_interest=[],
            error=f"No fue posible evaluar la malla multivariable: {exc}",
        )

    z_clean: list[list[float | None]] = []
    for row in zz:
        clean_row: list[float | None] = []
        for val in row:
            if np.isreal(val) and np.isfinite(val) and abs(float(val)) <= 1e4:
                clean_row.append(round(float(val), 5))
            else:
                clean_row.append(None)
        z_clean.append(clean_row)

    traces: list[dict[str, Any]] = []
    label = active_specs[0].label or f"z = {raw_expr}"

    if request.mode == "3d":
        traces.append(
            {
                "type": "surface",
                "x": xs.tolist(),
                "y": ys.tolist(),
                "z": z_clean,
                "name": label,
                "colorscale": "Viridis",
                "opacity": 0.9,
                "showscale": False,
            }
        )
    else:
        traces.append(
            {
                "type": "contour",
                "x": xs.tolist(),
                "y": ys.tolist(),
                "z": z_clean,
                "name": label,
                "colorscale": "YlGnBu",
                "contours": {"coloring": "heatmap", "showlabels": True},
                "line": {"smoothing": 0.85, "width": 1.2},
            }
        )

    # Análisis simbólico multivariable en (x0, y0) usando las operaciones del dominio
    x0 = float(request.point_x0)
    y0 = float(request.point_y0)
    mv_summary: dict[str, str] = {}
    step_gen = DerivativeStepGenerator(adapter)

    try:
        fx = sp.simplify(sp.diff(sym_expr, x_sym))
        fy = sp.simplify(sp.diff(sym_expr, y_sym))
        mv_summary["fx_latex"] = sp.latex(fx)
        mv_summary["fy_latex"] = sp.latex(fy)

        # Usar solve_gradient y solve_laplacian cuando no hay parámetros libres
        if not subs_map:
            grad_resp = solve_gradient(
                ast_node, {"variables": ["x", "y"]}, adapter, step_gen
            )
            lap_resp = solve_laplacian(
                ast_node, {"variables": ["x", "y"]}, adapter, step_gen
            )
            if grad_resp.calculation and grad_resp.calculation.primary_result:
                mv_summary["gradient_latex"] = (
                    grad_resp.calculation.primary_result.value.latex
                )
            if lap_resp.calculation and lap_resp.calculation.primary_result:
                mv_summary["laplacian_latex"] = (
                    lap_resp.calculation.primary_result.value.latex
                )
        else:
            mv_summary["gradient_latex"] = sp.latex(sp.Matrix([fx, fy]))
            mv_summary["laplacian_latex"] = sp.latex(
                sp.simplify(sp.diff(fx, x_sym) + sp.diff(fy, y_sym))
            )

        # Evaluar en (x0, y0)
        z0_val = sym_expr.subs({x_sym: x0, y_sym: y0}).evalf()
        fx0_val = fx.subs({x_sym: x0, y_sym: y0}).evalf()
        fy0_val = fy.subs({x_sym: x0, y_sym: y0}).evalf()

        if z0_val.is_real and fx0_val.is_real and fy0_val.is_real:
            z0_f = float(z0_val)
            fx0_f = float(fx0_val)
            fy0_f = float(fy0_val)
            mv_summary["point_value"] = f"f({x0:g}, {y0:g}) = {z0_f:.4g}"
            mv_summary["gradient_at_point"] = (
                f"∇f({x0:g}, {y0:g}) = ⟨{fx0_f:.4g}, {fy0_f:.4g}⟩"
            )

            tangent_plane_expr = sp.simplify(
                sp.Float(round(z0_f, 4))
                + sp.Float(round(fx0_f, 4)) * (x_sym - sp.Float(round(x0, 4)))
                + sp.Float(round(fy0_f, 4)) * (y_sym - sp.Float(round(y0, 4)))
            )
            mv_summary["tangent_plane_latex"] = f"z = {sp.latex(tangent_plane_expr)}"

            if request.mode == "3d":
                traces.append(
                    {
                        "type": "scatter3d",
                        "x": [x0],
                        "y": [y0],
                        "z": [z0_f],
                        "mode": "markers+text",
                        "text": [f"P({x0:g}, {y0:g}, {z0_f:.3g})"],
                        "textposition": "top center",
                        "marker": {"size": 6, "color": "#D55E00"},
                        "name": "Punto evaluado P₀",
                    }
                )
                if request.show_tangent_plane_3d:
                    tp_z = (z0_f + fx0_f * (xx - x0) + fy0_f * (yy - y0)).tolist()
                    traces.append(
                        {
                            "type": "surface",
                            "x": xs.tolist(),
                            "y": ys.tolist(),
                            "z": tp_z,
                            "name": f"Plano tangente en ({x0:g}, {y0:g})",
                            "opacity": 0.45,
                            "showscale": False,
                            "colorscale": [[0, "#D55E00"], [1, "#E69F00"]],
                        }
                    )
            else:
                # En modo contorno: marcar P0 y el vector gradiente
                traces.append(
                    {
                        "type": "scatter",
                        "x": [x0],
                        "y": [y0],
                        "mode": "markers+text",
                        "text": [f"P₀({x0:g}, {y0:g})"],
                        "textposition": "top right",
                        "marker": {
                            "size": 10,
                            "color": "#D55E00",
                            "line": {"color": "#FFFFFF", "width": 2},
                        },
                        "name": f"Punto ({x0:g}, {y0:g})",
                    }
                )
                norm_g = float(np.hypot(fx0_f, fy0_f))
                if norm_g > 1e-6:
                    scale = 0.18 * (x_max - x_min) / norm_g
                    gx_end = x0 + fx0_f * scale
                    gy_end = y0 + fy0_f * scale
                    traces.append(
                        {
                            "type": "scatter",
                            "x": [x0, gx_end],
                            "y": [y0, gy_end],
                            "mode": "lines+markers",
                            "line": {"color": "#D55E00", "width": 3},
                            "marker": {"size": [6, 9], "color": "#D55E00"},
                            "name": f"Dirección ∇f({x0:g}, {y0:g})",
                        }
                    )
    except Exception:
        pass

    # También validar punto con solve_multivariable_value si es aplicable
    if not subs_map:
        try:
            val_resp = solve_multivariable_value(
                ast_node,
                {"variables": ["x", "y"], "point": {"x": x0, "y": y0}},
                adapter,
            )
            if val_resp.calculation and val_resp.calculation.primary_result:
                mv_summary["exact_point_latex"] = (
                    val_resp.calculation.primary_result.value.latex
                )
        except Exception:
            pass

    mode_title = "Superficie 3D" if request.mode == "3d" else "Mapa de contorno 2D"
    summary_text = (
        f"{mode_title} de z = {raw_expr} en "
        f"[{x_min:g}, {x_max:g}] × [{y_min:g}, {y_max:g}]. "
        + mv_summary.get("point_value", "")
        + (
            " · " + mv_summary["gradient_at_point"]
            if "gradient_at_point" in mv_summary
            else ""
        )
    )

    return StudioResult(
        mode=request.mode,
        traces=traces,
        layout_hints={
            "mode": request.mode,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        },
        detected_parameters=detected_params,
        points_of_interest=[],
        primary_latex=f"z(x, y) = {sp.latex(sym_expr)}",
        derivative_latex=(
            f"\\nabla f(x, y) = {mv_summary.get('gradient_latex', '')}"
            if mv_summary.get("gradient_latex")
            else ""
        ),
        tangent_latex=mv_summary.get("tangent_plane_latex", ""),
        taylor_latex=(
            f"\\nabla^2 f(x, y) = {mv_summary.get('laplacian_latex', '')}"
            if mv_summary.get("laplacian_latex")
            else ""
        ),
        multivariable_summary=mv_summary,
        table_headers=["x", "y", "z = f(x, y)"],
        table_rows=_build_multivariable_table(sym_expr, x_sym, y_sym, x0, y0),
        accessible_summary=summary_text.strip(),
        warnings=warnings,
    )


def _build_multivariable_table(
    sym_expr: sp.Basic,
    x_sym: sp.Symbol,
    y_sym: sp.Symbol,
    x0: float,
    y0: float,
) -> list[list[str]]:
    """Construye una tabla compacta alrededor del punto (x0, y0)."""
    rows: list[list[str]] = []
    offsets = (-1.0, 0.0, 1.0)
    for dx in offsets:
        for dy in offsets:
            px = round(x0 + dx, 4)
            py = round(y0 + dy, 4)
            try:
                val = sym_expr.subs({x_sym: px, y_sym: py}).evalf()
                z_str = (
                    f"{float(val):.4g}"
                    if val.is_real and val.is_finite
                    else "Indefinido"
                )
            except Exception:
                z_str = "Indefinido"
            rows.append([f"{px:g}", f"{py:g}", z_str])
    return rows


def evaluate_studio_request(request: StudioRequest) -> StudioResult:
    """
    Evalúa de forma integral una solicitud del Estudio Gráfico (2D, Contorno o 3D),
    generando las trazas Plotly, los puntos notables, las herramientas de cálculo y
    la tabla de valores.
    """
    parser = MathParser()
    adapter = SympyAdapter()

    if request.mode in {"3d", "contour"}:
        return _evaluate_3d_or_contour(request, parser, adapter)

    all_raw_exprs = [s.expression for s in request.expressions if s.expression.strip()]
    detected_params = detect_free_parameters(all_raw_exprs, mode="2d")

    active_specs = [
        s for s in request.expressions if s.visible and s.expression.strip()
    ]
    if not active_specs:
        return StudioResult(
            mode="2d",
            traces=[],
            layout_hints={},
            detected_parameters=detected_params,
            points_of_interest=[],
            error="Agrega o activa al menos una función f(x) para graficar.",
        )

    x_min = float(min(request.x_min, request.x_max - 0.5))
    x_max = float(max(request.x_max, x_min + 0.5))
    samples = np.linspace(x_min, x_max, 450)
    var = sp.Symbol("x", real=True)

    traces: list[dict[str, Any]] = []
    parsed_series: list[
        tuple[FunctionExpressionSpec, sp.Basic, list[float | None]]
    ] = []
    warnings: list[str] = []

    for idx, spec in enumerate(active_specs):
        norm_text = _normalize_expression_text(spec.expression)
        try:
            ast_node = parser.parse(norm_text)
            sym_expr = adapter.ast_to_sympy(ast_node)
        except Exception as exc:
            warnings.append(f"No se pudo interpretar '{spec.expression}': {exc}")
            continue

        # Sustituir sliders activos
        subs_map: dict[sp.Symbol, float | sp.Symbol] = {}
        for sym in list(sym_expr.free_symbols):
            sname = str(sym)
            if sname == "x":
                subs_map[sym] = var
            elif sname not in RESERVED_CONSTANTS:
                subs_map[sym] = float(request.sliders.get(sname, 1.0))
        if subs_map:
            sym_expr = sym_expr.subs(subs_map)

        ys = _evaluate_1d_safe(sym_expr, var, samples)
        color = spec.color or SERIES_PALETTE[idx % len(SERIES_PALETTE)]
        series_label = spec.label or f"f{idx + 1}(x) = {norm_text}"

        traces.append(
            {
                "x": samples.tolist(),
                "y": ys,
                "mode": "lines",
                "name": series_label,
                "connectgaps": False,
                "line": {
                    "color": color,
                    "width": 2.6 if idx == 0 else 2.2,
                    "dash": spec.line_dash or "solid",
                },
            }
        )
        parsed_series.append((spec, sym_expr, ys))

    if not parsed_series:
        return StudioResult(
            mode="2d",
            traces=[],
            layout_hints={},
            detected_parameters=detected_params,
            points_of_interest=[],
            warnings=warnings,
            error=warnings[0] if warnings else "No se pudo evaluar ninguna expresión.",
        )

    primary_spec, primary_expr, primary_ys = parsed_series[0]
    primary_latex = f"f_1(x) = {sp.latex(primary_expr)}"
    derivative_latex = ""
    tangent_latex = ""
    normal_latex = ""
    taylor_latex = ""
    integral_exact_latex = ""
    integral_numeric: float | None = None
    riemann_numeric: float | None = None

    calc = request.calculus
    deriv_expr = sp.simplify(sp.diff(primary_expr, var))
    derivative_latex = f"f_1'(x) = {sp.latex(deriv_expr)}"

    # 1. Superposición de la derivada f'(x)
    if calc.show_derivative:
        deriv_ys = _evaluate_1d_safe(deriv_expr, var, samples)
        traces.append(
            {
                "x": samples.tolist(),
                "y": deriv_ys,
                "mode": "lines",
                "name": f"Derivada f₁'(x) = {deriv_expr}",
                "connectgaps": False,
                "line": {"color": "#0072B2", "width": 2.0, "dash": "dash"},
            }
        )

    # 2. Recta tangente y normal en x = x0
    if calc.tangent_enabled:
        x0 = float(calc.tangent_x0)
        y0_vals = _evaluate_1d_safe(primary_expr, var, np.array([x0]))
        m_vals = _evaluate_1d_safe(deriv_expr, var, np.array([x0]))
        if y0_vals and y0_vals[0] is not None and m_vals and m_vals[0] is not None:
            y0_f = float(y0_vals[0])
            m_f = float(m_vals[0])
            tang_expr = sp.simplify(
                sp.Float(round(y0_f, 4))
                + sp.Float(round(m_f, 4)) * (var - sp.Float(round(x0, 4)))
            )
            tangent_latex = f"y_T(x) = {sp.latex(tang_expr)} \\quad (m = {m_f:.4g})"
            tang_ys = [round(y0_f + m_f * (float(x_v) - x0), 5) for x_v in samples]
            traces.append(
                {
                    "x": samples.tolist(),
                    "y": tang_ys,
                    "mode": "lines",
                    "name": f"Tangente en x₀={x0:g} (m={m_f:.3g})",
                    "line": {"color": "#D55E00", "width": 2.0, "dash": "dot"},
                }
            )
            if calc.show_normal and abs(m_f) > 1e-6:
                m_norm = -1.0 / m_f
                norm_expr = sp.simplify(
                    sp.Float(round(y0_f, 4))
                    + sp.Float(round(m_norm, 4)) * (var - sp.Float(round(x0, 4)))
                )
                normal_latex = f"y_N(x) = {sp.latex(norm_expr)}"
                norm_ys = [
                    round(y0_f + m_norm * (float(x_v) - x0), 5) for x_v in samples
                ]
                traces.append(
                    {
                        "x": samples.tolist(),
                        "y": norm_ys,
                        "mode": "lines",
                        "name": f"Normal en x₀={x0:g}",
                        "line": {"color": "#AA3377", "width": 1.7, "dash": "dashdot"},
                    }
                )
            traces.append(
                {
                    "x": [x0],
                    "y": [y0_f],
                    "mode": "markers+text",
                    "text": [f"T({x0:g}, {y0_f:.3g})"],
                    "textposition": "top center",
                    "marker": {
                        "size": 9,
                        "color": "#D55E00",
                        "line": {"color": "#FFFFFF", "width": 2},
                    },
                    "name": f"Punto de tangencia ({x0:g}, {y0_f:.3g})",
                }
            )

    # 3. Polinomio de Taylor Tn(x; x0)
    if calc.taylor_enabled:
        try:
            t_order = max(1, min(int(calc.taylor_order), 9))
            t_x0 = float(calc.taylor_x0)
            taylor_poly = sp.series(primary_expr, var, t_x0, t_order + 1).removeO()
            taylor_latex = f"T_{{{t_order}}}(x; {t_x0:g}) = {sp.latex(taylor_poly)}"
            taylor_ys = _evaluate_1d_safe(taylor_poly, var, samples)
            traces.append(
                {
                    "x": samples.tolist(),
                    "y": taylor_ys,
                    "mode": "lines",
                    "name": f"Taylor grado {t_order} en x₀={t_x0:g}",
                    "connectgaps": False,
                    "line": {"color": "#AA3377", "width": 2.1, "dash": "dashdot"},
                }
            )
        except Exception:
            warnings.append(
                "No se pudo construir el desarrollo de Taylor en el punto elegido."
            )

    # 4. Integral definida [a, b] y Sumas de Riemann
    if calc.integral_enabled:
        ia = float(calc.integral_a)
        ib = float(calc.integral_b)
        low_i, high_i = (ia, ib) if ia <= ib else (ib, ia)
        area_samples = np.linspace(low_i, high_i, 160)
        area_ys = _evaluate_1d_safe(primary_expr, var, area_samples)
        traces.append(
            {
                "x": area_samples.tolist(),
                "y": area_ys,
                "mode": "lines",
                "fill": "tozeroy",
                "fillcolor": "rgba(33, 102, 83, 0.18)",
                "line": {"color": "rgba(33, 102, 83, 0.55)", "width": 1.2},
                "name": f"Área ∫[{ia:g}, {ib:g}] f₁(x)dx",
                "connectgaps": False,
            }
        )
        try:
            valid_pairs = [
                (float(x_v), float(y_v))
                for x_v, y_v in zip(area_samples, area_ys, strict=False)
                if y_v is not None
            ]
            if len(valid_pairs) >= 2:
                xs_int = np.array([p[0] for p in valid_pairs])
                ys_int = np.array([p[1] for p in valid_pairs])
                sign_int = 1.0 if ia <= ib else -1.0
                integral_numeric = round(
                    sign_int * float(np.trapezoid(ys_int, xs_int)), 6
                )
        except Exception:
            pass

        try:
            sym_int = sp.integrate(
                primary_expr, (var, sp.Float(round(ia, 4)), sp.Float(round(ib, 4)))
            )
            int_prefix = f"\\int_{{{ia:g}}}^{{{ib:g}}} f_1(x)\\,dx"
            if not sym_int.has(sp.Integral):
                integral_exact_latex = (
                    f"{int_prefix} = {sp.latex(sp.simplify(sym_int))}"
                )
            elif integral_numeric is not None:
                integral_exact_latex = f"{int_prefix} \\approx {integral_numeric:.5g}"
        except Exception:
            if integral_numeric is not None:
                int_prefix = f"\\int_{{{ia:g}}}^{{{ib:g}}} f_1(x)\\,dx"
                integral_exact_latex = f"{int_prefix} \\approx {integral_numeric:.5g}"

        if calc.riemann_enabled:
            r_traces, r_sum = _build_riemann_traces_and_sum(
                primary_expr, var, ia, ib, calc.riemann_n, calc.riemann_rule
            )
            traces.extend(r_traces)
            riemann_numeric = r_sum

    # 5. Puntos notables (estilo Desmos)
    points_of_interest: list[PointOfInterest] = []
    if calc.show_points_of_interest:
        points_of_interest = _compute_points_of_interest(
            parsed_series, var, samples, x_min, x_max
        )
        if points_of_interest:
            traces.append(
                {
                    "x": [p.x for p in points_of_interest],
                    "y": [p.y for p in points_of_interest],
                    "mode": "markers",
                    "text": [
                        f"{p.label} — {p.series_name}" for p in points_of_interest
                    ],
                    "hoverinfo": "text",
                    "marker": {
                        "size": 8,
                        "color": "#FFFFFF",
                        "line": {"color": "#24332F", "width": 2.2},
                    },
                    "name": "Puntos notables",
                }
            )

    # 6. Tabla de valores (estilo Desmos)
    t_headers, t_rows = _build_values_table(
        parsed_series,
        var,
        request.table_start,
        request.table_end,
        request.table_step,
    )

    summary_parts = [
        f"Gráfica 2D con {len(parsed_series)} función(es) activa(s) "
        f"en x ∈ [{x_min:g}, {x_max:g}]."
    ]
    if points_of_interest:
        summary_parts.append(
            f"{len(points_of_interest)} punto(s) notable(s) detectado(s)."
        )
    if integral_numeric is not None:
        summary_parts.append(
            f"Integral en [{calc.integral_a:g}, {calc.integral_b:g}] "
            f"≈ {integral_numeric:.4g}."
        )
    if riemann_numeric is not None:
        summary_parts.append(
            f"Suma de Riemann (n={calc.riemann_n}) ≈ {riemann_numeric:.4g}."
        )

    return StudioResult(
        mode="2d",
        traces=traces,
        layout_hints={"mode": "2d", "x_min": x_min, "x_max": x_max},
        detected_parameters=detected_params,
        points_of_interest=points_of_interest,
        primary_latex=primary_latex,
        derivative_latex=derivative_latex,
        tangent_latex=tangent_latex,
        normal_latex=normal_latex,
        taylor_latex=taylor_latex,
        integral_exact_latex=integral_exact_latex,
        integral_numeric=integral_numeric,
        riemann_numeric=riemann_numeric,
        table_headers=t_headers,
        table_rows=t_rows,
        accessible_summary=" ".join(summary_parts),
        warnings=warnings,
    )


def _build_values_table(
    parsed_series: list[tuple[FunctionExpressionSpec, sp.Basic, list[float | None]]],
    var: sp.Symbol,
    start: float,
    end: float,
    step: float,
) -> tuple[list[str], list[list[str]]]:
    """Construye la tabla numérica (x, f1(x), f2(x), ...) estilo Desmos."""
    headers = ["x"] + [
        spec.label or f"f{idx + 1}(x)" for idx, (spec, _, _) in enumerate(parsed_series)
    ]
    if step <= 0:
        step = 1.0
    low, high = (start, end) if start <= end else (end, start)
    count = int(min(50, max(2, round((high - low) / step) + 1)))
    xs = np.linspace(low, low + step * (count - 1), count)

    series_evals = [_evaluate_1d_safe(expr, var, xs) for _, expr, _ in parsed_series]
    rows: list[list[str]] = []
    for row_idx, x_val in enumerate(xs):
        row = [f"{round(float(x_val), 4):g}"]
        for col_eval in series_evals:
            y_val = col_eval[row_idx]
            if y_val is None:
                row.append("Indefinido")
            else:
                row.append(f"{round(float(y_val), 5):g}")
        rows.append(row)

    return headers, rows
