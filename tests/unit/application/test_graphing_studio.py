"""Pruebas unitarias del motor Estudio Gráfico (GeoGebra + Desmos)."""

from src.application.graphing_studio import (
    STUDIO_PRESETS,
    CalculusOverlayConfig,
    FunctionExpressionSpec,
    StudioRequest,
    detect_free_parameters,
    evaluate_studio_request,
)


def test_detect_free_parameters_2d_and_3d():
    params_2d = detect_free_parameters(["a * sin(b * x) + c", "x^2 + pi"], mode="2d")
    assert params_2d == ["a", "b", "c"]

    params_3d = detect_free_parameters(["k * (x^2 - y^2) + m"], mode="3d")
    assert params_3d == ["k", "m"]


def test_evaluate_studio_request_2d_calculus_and_notable_points():
    request = StudioRequest(
        mode="2d",
        expressions=(
            FunctionExpressionSpec("f1", "x^3 - 3*x", "f₁(x)"),
            FunctionExpressionSpec("f2", "x", "f₂(x)"),
        ),
        x_min=-3.5,
        x_max=3.5,
        calculus=CalculusOverlayConfig(
            show_points_of_interest=True,
            show_derivative=True,
            tangent_enabled=True,
            tangent_x0=1.5,
            show_normal=True,
            integral_enabled=True,
            integral_a=0.0,
            integral_b=2.0,
            riemann_enabled=True,
            riemann_rule="midpoint",
            riemann_n=8,
            taylor_enabled=True,
            taylor_order=3,
            taylor_x0=0.0,
        ),
        table_start=-1.0,
        table_end=1.0,
        table_step=1.0,
    )
    result = evaluate_studio_request(request)

    assert result.error is None
    assert len(result.traces) >= 7
    assert result.derivative_latex
    assert result.tangent_latex
    assert result.normal_latex
    assert result.taylor_latex
    assert result.integral_exact_latex
    assert result.integral_numeric is not None
    assert result.riemann_numeric is not None

    kinds = {pt.kind for pt in result.points_of_interest}
    assert {"y_intercept", "root", "local_min", "local_max", "intersection"} <= kinds
    assert result.table_headers == ["x", "f₁(x)", "f₂(x)"]
    assert len(result.table_rows) == 3


def test_evaluate_studio_request_3d_and_contour_multivariable():
    for mode in ("3d", "contour"):
        request = StudioRequest(
            mode=mode,
            expressions=(FunctionExpressionSpec("s1", "x^2 - y^2", "Silla"),),
            x_min=-3.0,
            x_max=3.0,
            y_min=-3.0,
            y_max=3.0,
            point_x0=2.0,
            point_y0=1.0,
            show_tangent_plane_3d=True,
        )
        result = evaluate_studio_request(request)
        assert result.error is None
        assert result.traces
        assert "gradient_latex" in result.multivariable_summary
        assert "laplacian_latex" in result.multivariable_summary
        assert "tangent_plane_latex" in result.multivariable_summary
        assert len(result.table_rows) == 9


def test_all_studio_presets_evaluate_cleanly():
    for preset in STUDIO_PRESETS:
        specs = tuple(
            FunctionExpressionSpec(f"f{i + 1}", expr)
            for i, expr in enumerate(preset.expressions)
        )
        req = StudioRequest(
            mode=preset.mode,
            expressions=specs,
            sliders=preset.sliders,
            x_min=preset.x_min,
            x_max=preset.x_max,
            calculus=preset.calculus,
        )
        res = evaluate_studio_request(req)
        assert res.error is None
        assert res.traces

