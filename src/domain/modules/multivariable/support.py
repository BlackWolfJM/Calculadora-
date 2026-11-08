from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

import sympy as sp

from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.steps import (
    EducationalStep,
    StepCoverage,
    StepOutcome,
    StepStatus,
)

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


def require_identifier(value: object, *, field: str) -> str:
    """Valida que el valor sea un identificador seguro."""
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} debe ser un identificador matemático válido.")
    return value


def require_variables(
    raw: object, *, dimensions: tuple[int, ...] = (2, 3)
) -> tuple[str, ...]:
    """Valida una lista de nombres de variables."""
    if not isinstance(raw, (list, tuple)) or len(raw) not in dimensions:
        raise ValueError(f"variables debe contener {dimensions} nombres.")
    values = tuple(require_identifier(v, field="variable") for v in raw)
    if len(set(values)) != len(values):
        raise ValueError("Las variables deben ser distintas.")
    return values


def require_vector(v: sp.Matrix, *, dimensions: tuple[int, ...] = (2, 3)) -> sp.Matrix:
    """Valida que la entrada de sympy sea un vector columna de la dimensión esperada."""
    if not isinstance(v, sp.MatrixBase) or v.cols != 1 or v.rows not in dimensions:
        raise ValueError(f"Se esperaba un vector columna de dimensión {dimensions}.")
    return sp.Matrix(v)


def _safe_number(value: object) -> sp.Number:
    """Valida de forma estricta que las coordenadas del usuario sean números."""
    if isinstance(value, bool):
        raise ValueError("Los booleanos no son coordenadas numéricas.")
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float) and sp.Float(value).is_finite:
        return sp.Float(value)
    raise ValueError("Cada coordenada debe ser int o float finito.")


def step(
    step_id: str,
    rule: str,
    explanation: str,
    before: sp.Basic | str,
    after: sp.Basic | str,
    sub_steps: list[EducationalStep] | None = None,
) -> EducationalStep:
    """Crea un paso educativo."""
    before_latex = before if isinstance(before, str) else sp.latex(before)
    after_latex = after if isinstance(after, str) else sp.latex(after)
    return EducationalStep(
        step_id, rule, explanation, before_latex, after_latex, sub_steps=sub_steps or []
    )


def response(
    label: str,
    result: sp.Basic,
    steps: Sequence[EducationalStep],
    *,
    verification: str | None = None,
    coverage: StepCoverage = StepCoverage.COMPLETE,
    warnings: Sequence[str] = (),
) -> SolutionResponse:
    """Formatea la respuesta final unificada."""
    status = (
        ResolutionStatus.SUCCESS
        if coverage is StepCoverage.COMPLETE
        else ResolutionStatus.PARTIAL
    )
    step_status = (
        StepStatus.SUCCESS
        if coverage is not StepCoverage.UNAVAILABLE
        else StepStatus.UNSUPPORTED
    )
    return SolutionResponse(
        response_id=str(uuid.uuid4()),
        status=status,
        calculation=CalculationBlock(
            status=status.value,
            primary_result=ResultItem(
                value=MathPayload(canonical_text=str(result), latex=sp.latex(result)),
                label=label,
            ),
        ),
        procedure=StepOutcome(step_status, coverage, list(steps)),
        verification=verification,
        warnings=list(warnings),
    )


def primary_text(result: SolutionResponse) -> str:
    """Ayuda de pruebas; extrae el texto del resultado."""
    assert result.calculation is not None
    assert result.calculation.primary_result is not None
    return result.calculation.primary_result.value.canonical_text
