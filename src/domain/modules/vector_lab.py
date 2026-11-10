"""Núcleo algebraico del laboratorio vectorial (lote 01.01–01.10).

Sin dependencia de Qt; preserva resultados exactos mediante SymPy.
Los símbolos admitidos son expresiones SymPy construidas por el llamador,
no texto Python evaluado dinámicamente.
"""
from dataclasses import dataclass
from typing import Sequence

import sympy as sp

from src.domain.steps import EducationalStep


@dataclass(frozen=True)
class VectorResult:
    subtopic: str
    title: str
    value: str
    latex: str
    steps: tuple[EducationalStep, ...]
    arrows: tuple[tuple[str, tuple[float, float], tuple[float, float]], ...]
    note: str = ""


SUBTOPICS = {
    "01.01": "Escalares y vectores",
    "01.02": "Coordenadas cartesianas",
    "01.03": "Puntos frente a vectores",
    "01.04": "Componentes vectoriales",
    "01.05": "Posición y desplazamiento",
    "01.06": "Igualdad de vectores",
    "01.07": "Suma y resta",
    "01.08": "Multiplicación por escalar",
    "01.09": "Propiedades algebraicas",
    "01.10": "Combinaciones lineales y colinealidad",
}


def _vector(values: Sequence[sp.Expr]) -> sp.Matrix:
    if len(values) not in (2, 3):
        raise ValueError("Se requieren dos o tres componentes.")
    vector = sp.Matrix([sp.sympify(item) for item in values])
    for item in vector:
        if item.is_real is not True:
            raise ValueError("Las componentes deben ser reales y determinadas.")
        if item.is_finite is not True:
            raise ValueError("No se admiten componentes infinitas o indeterminadas.")
    return vector


def _float_pair(v: sp.Matrix) -> tuple[float, float]:
    return (float(v[0]), float(v[1]))


def _arrow(label: str, start: sp.Matrix, end: sp.Matrix):
    return (label, _float_pair(start), _float_pair(end))


def _step(index: int, title: str, explanation: str, before: str, after: str):
    return EducationalStep(
        step_id=f"vector-{index}", rule_name=title,
        explanation=explanation, before_latex=before, after_latex=after,
    )


def calculate(
    subtopic: str,
    a: Sequence[sp.Expr] = (3, 2),
    b: Sequence[sp.Expr] = (-1, 4),
    scalar: sp.Expr = sp.Integer(2),
    operation: str = "sum",
) -> VectorResult:
    """Resuelve una actividad del primer lote y produce pasos inspeccionables.

    La visualización de flechas proyecta únicamente las primeras dos
    componentes; el resultado algebraico mantiene la tercera componente.
    """
    if subtopic not in SUBTOPICS:
        raise ValueError("Subtema fuera del lote 1.")
    u, v = _vector(a), _vector(b)
    if u.rows != v.rows:
        raise ValueError("Ambos vectores deben tener la misma dimensión.")
    k = sp.sympify(scalar)
    if k.is_real is not True or k.is_finite is not True:
        raise ValueError("El escalar debe ser un número real finito.")
    origin = sp.zeros(u.rows, 1)
    steps: list[EducationalStep] = []
    arrows: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    note = ""
    result: sp.Expr | sp.Matrix | str
    title = SUBTOPICS[subtopic]
    uv = sp.latex(u.T)
    vv = sp.latex(v.T)

    if subtopic == "01.01":
        result = "Escalar: magnitud sin dirección; vector: magnitud y dirección."
        note = "Ejemplos: temperatura (°C) es escalar; desplazamiento (m) es vector."
        arrows = [_arrow("Desplazamiento", origin, u)]
        steps.append(_step(1, "Identificación",
            "Una flecha representa componentes y sentido; un escalar se representa por un valor.",
            r"s=2", r"\vec{u}=" + uv))
    elif subtopic == "01.02":
        result = u
        arrows = [_arrow("P", origin, u)]
        signs = tuple(int(sp.sign(x)) for x in u)
        if 0 in signs:
            note = "El punto pertenece a un eje o plano coordenado."
        elif u.rows == 2:
            quadrants = {(1, 1): "I", (-1, 1): "II",
                         (-1, -1): "III", (1, -1): "IV"}
            note = f"Cuadrante {quadrants[signs]}."
        else:
            note = "Signos del octante (x,y,z): " + str(signs)
        steps.append(_step(1, "Localización",
            "Ubicamos el punto usando sus coordenadas con signo.",
            r"P=(x,y,z)" if u.rows == 3 else r"P=(x,y)",
            r"P=" + uv))
    elif subtopic == "01.03":
        result = u
        arrows = [_arrow("Vector libre", origin, u), _arrow("Vector trasladado", v, v + u)]
        steps.append(_step(1, "Traslación",
            "La flecha cambia de origen, pero el desplazamiento extremo menos origen sigue siendo u.",
            sp.latex((v + u).T) + "-" + vv, uv))
    elif subtopic == "01.04":
        result = u
        arrows = [_arrow("u", origin, u)]
        for i in range(u.rows):
            component = sp.zeros(u.rows, 1)
            component[i] = u[i]
            arrows.append(_arrow(("x", "y", "z")[i], origin, component))
        note = "Las componentes son coeficientes de la base cartesiana i, j, k."
        steps.append(_step(1, "Descomposición",
            "Cada componente multiplica su vector canónico correspondiente.",
            uv, "+".join(f"({sp.latex(u[i])}){axis}" for i, axis in enumerate(
                (r"\mathbf{i}", r"\mathbf{j}", r"\mathbf{k}")[:u.rows]))))
    elif subtopic == "01.05":
        result = v - u
        arrows = [_arrow("A", origin, u), _arrow("B", origin, v), _arrow("B-A", u, v)]
        d = sp.sqrt(sum(x*x for x in v-u))
        note = f"Distancia entre A y B: {sp.sstr(sp.simplify(d))}"
        steps.append(_step(1, "Desplazamiento",
            "Restamos las componentes del punto inicial a las del final.",
            vv + "-" + uv, sp.latex(result.T)))
        steps.append(_step(2, "Distancia",
            "La distancia euclidiana es la norma del desplazamiento.",
            r"\|B-A\|", sp.latex(sp.simplify(d))))
    elif subtopic == "01.06":
        result = "Iguales" if u == v else "Distintos"
        arrows = [_arrow("u", origin, u), _arrow("v trasladado", u, u + v)]
        steps.append(_step(1, "Igualdad",
            "Dos vectores son iguales si todas sus componentes son iguales, aunque cambie su origen.",
            uv + "=" + vv + "?", (r"\mathrm{iguales}" if u == v else r"\mathrm{distintos}")))
    elif subtopic == "01.07":
        if operation not in ("sum", "difference"):
            raise ValueError("Operación admitida: sum o difference.")
        sign = 1 if operation == "sum" else -1
        result = u + sign*v
        arrows = [_arrow("u", origin, u), _arrow("v" if sign == 1 else "-v", u, result),
                  _arrow("resultante", origin, result),
                  _arrow("paralelogramo", v if sign == 1 else -v, result)]
        steps.append(_step(1, "Operación componente a componente",
            "Sumamos o restamos cada pareja de coordenadas sin mezclar ejes.",
            uv + ("+" if sign == 1 else "-") + vv, sp.latex(result.T)))
    elif subtopic == "01.08":
        result = k*u
        arrows = [_arrow("u", origin, u), _arrow("k·u", origin, result)]
        note = "k negativo invierte el sentido; k=0 produce el vector nulo."
        steps.append(_step(1, "Multiplicación",
            "Multiplicamos cada componente por el escalar.",
            sp.latex(k) + uv, sp.latex(result.T)))
    elif subtopic == "01.09":
        result = u+v
        arrows = [_arrow("u", origin, u), _arrow("v", u, u+v),
                  _arrow("u+v", origin, u+v)]
        steps.append(_step(1, "Conmutatividad",
            "Sumar componente a componente demuestra que u+v = v+u.",
            uv + "+" + vv, sp.latex((u+v).T)))
        steps.append(_step(2, "Distributividad",
            "El producto por escalar se distribuye sobre la suma.",
            sp.latex(k) + "(" + uv + "+" + vv + ")",
            sp.latex((k*u+k*v).T)))
        w = sp.ones(u.rows, 1)
        assert (u + v) + w == u + (v + w)
        note = "Asociatividad comprobada además con w=(1,…,1)."
    else:
        result = k*u + v
        arrows = [_arrow("k·u", origin, k*u), _arrow("v", k*u, result),
                  _arrow("combinación", origin, result)]
        matrix = u.row_join(v)
        rank = matrix.rank()
        is_collinear = rank <= 1
        note = f"Rango de [u v]: {rank}. " + (
            "Los vectores son linealmente dependientes."
            if is_collinear else "Los vectores son linealmente independientes.")
        steps.append(_step(1, "Combinación lineal",
            "Se escala u y se suma v componente a componente.",
            sp.latex(k) + uv + "+" + vv, sp.latex(result.T)))
        steps.append(_step(2, "Colinealidad",
            "Dos vectores son colineales exactamente cuando el rango de la matriz que forman es ≤ 1.",
            r"\operatorname{rang}([u\ v])", sp.latex(rank)))

    if isinstance(result, sp.MatrixBase):
        latex = sp.latex(result.T)
        value = sp.sstr(list(result))
    elif isinstance(result, str):
        latex = r"\text{" + result.replace(";", r"\;") + "}"
        value = result
    else:
        latex = sp.latex(result)
        value = sp.sstr(result)
    return VectorResult(subtopic, title, value, latex, tuple(steps), tuple(arrows), note)
