"""Versioned, local documents for the graphing workspace."""

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

_VERSION = 1
_MAX_FILE_BYTES = 256_000


@dataclass
class GraphSession:
    expressions: list[tuple[str, bool]] = field(default_factory=list)
    parameters: dict[str, float] = field(default_factory=dict)
    data: list[tuple[float, float]] = field(default_factory=list)
    mode: str = "2d"
    regression: str = "none"
    x_range: tuple[float, float] = (-10.0, 10.0)
    y_range: tuple[float, float] = (-10.0, 10.0)
    t_range: tuple[float, float] = (0.0, math.tau)


def _number(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            result = float(value)
        except OverflowError:
            pass
        else:
            if math.isfinite(result):
                return result
    raise ValueError("El archivo contiene un número inválido.")


def _pair(value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("El archivo contiene un par de valores inválido.")
    return _number(value[0]), _number(value[1])


def _bounds(value: object) -> tuple[float, float]:
    start, end = _pair(value)
    if start >= end or max(abs(start), abs(end)) > 10_000:
        raise ValueError("El intervalo debe ser creciente y estar entre ±10000.")
    return start, end


def _decode(payload: object) -> GraphSession:
    if not isinstance(payload, dict) or type(payload.get("version")) is not int:
        raise ValueError("El archivo no es una sesión de la graficadora.")
    if payload["version"] != _VERSION:
        raise ValueError("La versión de esta sesión no es compatible.")
    mode, regression = payload.get("mode"), payload.get("regression")
    if mode not in ("2d", "3d") or regression not in (
        "none", "linear", "quadratic", "cubic"
    ):
        raise ValueError("El modo de gráfica o el ajuste no es compatible.")
    raw_expressions = payload.get("expressions")
    if not isinstance(raw_expressions, list) or len(raw_expressions) > 24:
        raise ValueError("La lista de expresiones de la sesión es inválida.")
    expressions: list[tuple[str, bool]] = []
    for row in raw_expressions:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != 2
            or not isinstance(row[0], str)
            or len(row[0]) > 512
            or not isinstance(row[1], bool)
        ):
            raise ValueError("La sesión contiene una expresión inválida.")
        expressions.append((row[0], row[1]))
    raw_parameters, raw_data = payload.get("parameters"), payload.get("data")
    if not isinstance(raw_parameters, dict) or len(raw_parameters) > 26:
        raise ValueError("La sesión contiene parámetros inválidos.")
    parameters = {}
    for name, value in raw_parameters.items():
        if (
            not isinstance(name, str)
            or len(name) != 1
            or not name.isascii()
            or not name.isalpha()
        ):
            raise ValueError("La sesión contiene un nombre de parámetro inválido.")
        numeric = _number(value)
        if abs(numeric) > 1e12:
            raise ValueError("El parámetro de la sesión supera el intervalo admitido.")
        parameters[name] = numeric
    if not isinstance(raw_data, list) or len(raw_data) > 200:
        raise ValueError("La tabla de la sesión supera el límite de 200 pares.")
    return GraphSession(
        expressions=expressions,
        parameters=parameters,
        data=[_pair(row) for row in raw_data],
        mode=mode,
        regression=regression,
        x_range=_bounds(payload.get("x_range")),
        y_range=_bounds(payload.get("y_range")),
        t_range=_bounds(payload.get("t_range")),
    )


def load_graph_session(path: str | Path) -> GraphSession:
    """Validate the entire document before applying any state."""
    with Path(path).open("rb") as stream:
        raw = stream.read(_MAX_FILE_BYTES + 1)
    if len(raw) > _MAX_FILE_BYTES:
        raise ValueError("El archivo de sesión es demasiado grande.")
    try:
        return _decode(json.loads(raw.decode("utf-8-sig")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("El archivo no contiene una sesión JSON válida.") from exc


def save_graph_session(path: str | Path, session: GraphSession) -> None:
    """Replace the destination only after a complete, valid write."""
    payload = {"version": _VERSION, **asdict(session)}
    _decode(payload)
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode()
    if len(raw) > _MAX_FILE_BYTES:
        raise ValueError("La sesión es demasiado grande.")
    target = Path(path)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(raw)
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
