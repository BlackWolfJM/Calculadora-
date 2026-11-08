import json
from math import pi

import pytest

from src.infrastructure.graphing_workspace import build_graph, evaluate_function_table


def test_mixed_curves_and_slider_values():
    result = build_graph(
        [
            "y=a*x",
            "x^2+y^2=9",
            "y>x^2 { -2<x<2 }",
            "r=cos(3θ)",
            "(cos(t),sin(t))",
            "x=2",
            "sqrt(-1)",
            "y=3",
        ],
        {"a": 2},
        x_range=(-5, 5),
        t_range=(0, pi),
    )

    assert result.parameters == ("a",)
    assert 6 in result.errors
    assert result.traces[0]["y"][-1] == 10
    assert result.traces[1]["type"] == "contour"
    assert result.traces[2]["contours"]["operation"] == ">"
    assert all(row[0] is None for row in result.traces[2]["z"])
    assert result.traces[4]["x"][0] == 1
    assert result.traces[5]["x"][-1] == -1
    assert set(result.traces[6]["x"]) == {2}
    assert set(result.traces[-1]["y"]) == {3}
    json.dumps(result.traces, allow_nan=False)


def test_surface_and_parametric_curve_in_3d():
    result = build_graph(["z=sin(x)*cos(y)", "(cos(t),sin(t),t)", "(1,2,3)"], view="3d")

    assert not result.errors
    surface, curve, point = result.traces
    assert surface["type"] == "surface"
    assert len(surface["z"][0]) == len(surface["x"])
    assert len(surface["z"]) == len(surface["y"])
    assert curve["type"] == "scatter3d"
    assert point["z"] == [3]


def test_geometry_data_and_symbolic_calculus():
    result = build_graph(
        [
            "A=(0,0)",
            "B=(4,4)",
            "segment(A,B)",
            "circle(A,2)",
            "polygon(A,(0,4),B)",
            "midpoint(A,B)",
            "distance(A,B)",
            "line(A,B)",
            "intersection(A,B,(0,4),(4,0))",
            "table((0,1),(1,3),(2,5))",
            "fit((0,1),(1,3),(2,5))",
            "derivative(x^3)",
            "integral(x^2)",
        ]
    )

    assert not result.errors
    assert result.traces[0]["text"] == ["A"]
    assert result.traces[2]["x"] == [0, 4]
    assert result.traces[4]["fill"] == "toself"
    assert result.traces[5]["x"] == [2]
    assert "5.65685" in result.details[6]
    assert result.traces[7]["x"] == [2]
    assert result.traces[8]["y"] == [1, 3, 5]
    assert result.traces[9]["mode"] == "markers"
    assert result.traces[9]["y"] == [1, 3, 5]
    assert result.traces[10]["mode"] == "lines"
    assert "R²" in result.details[10]
    assert result.details[11] == "3*x^2"
    assert result.details[12] == "x^3/3 + C"


def test_singularities_and_bad_rows_stay_isolated():
    result = build_graph(["1/x", "x/x", "fit((2,1),(2,4))", "foo(x)", "y=2"])

    assert set(result.errors) == {2, 3}
    assert None in result.traces[0]["y"]
    assert None in result.traces[1]["y"]
    assert set(result.traces[-1]["y"]) == {2}


def test_hidden_named_points_still_supply_geometry_dependencies():
    result = build_graph(
        ["segment(A,B)", "A=(a,0)", "B=(0,1)", "wrong()"],
        {"a": 3},
        hidden_rows={1, 2, 3},
    )

    assert not result.errors
    assert result.parameters == ("a",)
    assert len(result.traces) == 1
    assert result.traces[0]["x"] == [3, 0]


def test_grouped_functions_and_symbolic_integral_keep_parameters():
    result = build_graph(
        ["(x+1)*(x-1)", "integral(a*x)", "integral((x+1)^100*x)"],
        {"a": 2},
    )

    assert result.traces[0]["y"][-1] == 99
    assert result.traces[1]["y"][-1] == 100
    assert result.details[1] == "a*x^2/2 + C"
    assert "grado" in result.errors[2]


def test_off_grid_even_pole_and_large_nested_constants():
    result = build_graph(["1/(x-0.01)^2", "((99999999^100)^100)^100"])

    assert None in result.traces[0]["y"]
    assert "anidadas" in result.errors[1]


def test_implicit_tangent_zero_sets_and_absent_regions():
    result = build_graph(
        [
            "(x^2+y^2-2)^2=0",
            "abs(x-0.123)=0",
            "x^2+y^2=-1",
            "x^2+y^2=0",
            "sqrt(x)=sqrt(x)",
            "x^2+y^2<-1",
        ]
    )

    assert not result.errors
    first, second, center = result.traces
    for trace in (first, second):
        assert trace["type"] == "contour"
        assert min(trace["z"][75]) < 0 < max(trace["z"][75])
    assert center["x"] == center["y"] == [0]
    assert "Sin soluciones" in result.details[2]
    assert "zona válida" in result.details[4]
    assert "Sin región" in result.details[5]


@pytest.mark.parametrize("bounds", [(2, -2), (0, float("inf")), (0, 0)])
def test_invalid_ranges(bounds):
    with pytest.raises(ValueError):
        build_graph(["x"], x_range=bounds)


def test_geogebra_tangent_normal_taylor_and_definite_integral():
    result = build_graph(
        [
            "tangent(x^2, 1)",
            "normal(x^2, 1)",
            "integral(4 - x^2, 0, 2)",
            "riemann(4 - x^2, 0, 2, 8, midpoint)",
            "taylor(sin(x), 0, 5)",
        ]
    )

    assert not result.errors
    assert "m = 2" in result.details[0]
    assert "m = -0.5" in result.details[1]
    assert "5.333" in result.details[2]
    assert "Suma (midpoint, n=8)" in result.details[3]
    assert "T_5(x)" in result.details[4]
    assert any(trace.get("fill") == "tozeroy" for trace in result.traces)
    assert any(trace.get("fill") == "toself" for trace in result.traces)


def test_desmos_roots_extrema_intersect_and_auto_notable_points():
    result = build_graph(
        [
            "y = x^3 - 3*x",
            "y = x",
            "roots(x^2 - 4)",
            "extrema(x^3 - 3*x)",
            "intersect(x^2, x + 2)",
        ],
        x_range=(-5, 5),
    )

    assert not result.errors
    assert "(-2, 0)" in result.details[2] and "(2, 0)" in result.details[2]
    assert "Mín" in result.details[3] and "Máx" in result.details[3]
    assert "(-1, 1)" in result.details[4] and "(2, 4)" in result.details[4]

    kinds = {pt["kind"] for pt in result.notable_points}
    assert {"y_intercept", "root", "local_min", "local_max", "intersection"} <= kinds


def test_multivariable_contour_gradient_and_3d_tangent_plane():
    res_2d = build_graph(
        [
            "contour(sin(x)*cos(y))",
            "gradient(x^2 + y^2, 1, 2)",
        ],
        view="2d",
    )
    assert not res_2d.errors
    assert res_2d.traces[0]["type"] == "contour"
    assert "∇f(1, 2) = (2, 4)" in res_2d.details[1]

    res_3d = build_graph(
        [
            "z = x^2 - y^2",
            "tangentplane(x^2 - y^2, 2, 1)",
        ],
        view="3d",
    )
    assert not res_3d.errors
    assert len(res_3d.traces) == 3
    assert "∇f(2,1) = (4, -2)" in res_3d.details[1]


def test_evaluate_function_table_desmos_style():
    headers, rows = evaluate_function_table(
        ["y = x^2", "y = 2*x + 1"],
        x_start=-1.0,
        x_end=1.0,
        step=1.0,
    )
    assert headers == ["x", "y = x^2", "y = 2*x + 1"]
    assert rows == [
        ["-1", "1", "-1"],
        ["0", "0", "1"],
        ["1", "1", "3"],
    ]


def test_inequality_boundaries_report_shaded_region():
    strict = build_graph(["y > x^2"])
    inclusive = build_graph(["y >= x^2"])

    assert "Frontera discontinua (estricta)" in strict.details[0]
    assert "Región sombreada" in strict.details[0]
    assert "Frontera continua (inclusiva)" in inclusive.details[0]
    assert "Región sombreada" in inclusive.details[0]


def test_solver_transfer_routes_inequalities_without_invalid_prefix():
    from src.presentation.graphing_workspace import GraphingWorkspace

    captured = {}

    class Tabs:
        def setCurrentIndex(self, index):
            self.index = index

    class Stub:
        _tabs = Tabs()

        def _apply_session(self, session):
            captured["session"] = session

    GraphingWorkspace.load_from_solver(Stub(), "x^2 < 4", "equations", "x")
    assert captured["session"].expressions == [("x^2 < 4", True)]

    GraphingWorkspace.load_from_solver(Stub(), "< x^2", "equations", "x")
    assert captured["session"].expressions == [("y < x^2", True)]

