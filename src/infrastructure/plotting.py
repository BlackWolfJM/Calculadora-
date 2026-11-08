"""Bounded-size plot payloads, computed only inside the calculation process."""

import numpy as np
import sympy as sp

from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def build_plot(expression, module_id, parameters, response):
    if (
        module_id not in {"derivatives", "integrals"}
        or response.status.value not in {"success", "success_with_warnings", "partial"}
        or not response.calculation
    ):
        return []
    adapter = SympyAdapter()
    original = adapter.ast_to_sympy(MathParser().parse(expression))
    var = sp.Symbol(parameters.get("variable", "x"), real=True)
    text = response.calculation.primary_result.value.canonical_text.removesuffix(" + C")
    symbols = {s.name: s for s in original.free_symbols}
    symbols[var.name] = var
    result = sp.sympify(text, locals=symbols)
    samples = np.linspace(-10, 10, 400)
    traces = []
    for expr, name in ((original, "Expresión original"), (result, "Resultado")):
        if expr.free_symbols - {var}:
            return []
        with np.errstate(all="ignore"):
            values = np.broadcast_to(
                sp.lambdify(var, expr, "numpy")(samples), samples.shape
            )
        clean = [float(y) if np.isreal(y) and np.isfinite(y) else None for y in values]
        singular = sp.singularities(expr, var)
        if isinstance(singular, sp.FiniteSet):
            for point in singular:
                if point.is_real and point.is_finite:
                    index = int(np.searchsorted(samples, float(point)))
                    if 0 < index < len(clean):
                        clean[index - 1 : index + 1] = [None, None]
        traces.append(
            {
                "x": samples.tolist(),
                "y": clean,
                "mode": "lines",
                "name": name,
                "connectgaps": False,
            }
        )
    return traces
