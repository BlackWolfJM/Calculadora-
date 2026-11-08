import json
import math

import pytest

from src.infrastructure.graph_session import (
    GraphSession,
    load_graph_session,
    save_graph_session,
)


def test_graph_session_restores_editable_state(tmp_path):
    target = tmp_path / "curvas.json"
    original = GraphSession(
        expressions=[("y=a·sin(x)", True), ("x^2+y^2=9", False)],
        parameters={"a": -1.25, "A": 1e8},
        data=[(-2.0, 3.5), (1.0, 2.5)],
        mode="3d",
        regression="linear",
        x_range=(-4.0, 5.0),
        y_range=(-3.0, 7.0),
        t_range=(-math.pi, math.pi),
    )
    save_graph_session(target, original)
    assert load_graph_session(target) == original


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("version", 9),
        ("expressions", [["x", 1]]),
        ("parameters", {"abc": 1}),
        ("data", [[0, float("inf")]]),
        ("x_range", [1, -1]),
    ],
)
def test_graph_session_rejects_invalid_fields(tmp_path, field, value):
    target = tmp_path / "curvas.json"
    save_graph_session(target, GraphSession())
    content = json.loads(target.read_text(encoding="utf-8"))
    content[field] = value
    target.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(ValueError):
        load_graph_session(target)


def test_invalid_graph_session_preserves_existing_file(tmp_path):
    target = tmp_path / "curvas.json"
    original = GraphSession(expressions=[("x", True)])
    save_graph_session(target, original)
    with pytest.raises(ValueError):
        save_graph_session(target, GraphSession(parameters={"a": float("nan")}))
    assert load_graph_session(target) == original
