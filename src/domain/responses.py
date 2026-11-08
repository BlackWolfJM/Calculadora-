from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.domain.errors import StructuredMathError
from src.domain.steps import StepOutcome


class ResolutionStatus(Enum):
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    PARTIAL = "partial"
    INVALID_INPUT = "invalid_input"
    AMBIGUOUS_INPUT = "ambiguous_input"
    UNSUPPORTED = "unsupported"
    UNEVALUATED = "unevaluated"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    FAILED = "failed"


@dataclass(frozen=True)
class MathPayload:
    """Envuelve la representación matemática en diferentes formatos."""

    canonical_text: str
    latex: str


@dataclass(frozen=True)
class ResultItem:
    value: MathPayload
    label: str


@dataclass(frozen=True)
class CalculationBlock:
    status: str
    primary_result: Optional[ResultItem]
    related_results: list[ResultItem] = field(default_factory=list)


@dataclass(frozen=True)
class SolutionResponse:
    """Contrato de respuesta estructurada común para todos los módulos."""

    response_id: str
    status: ResolutionStatus
    normalized_input: Optional[str] = None
    calculation: Optional[CalculationBlock] = None
    procedure: Optional[StepOutcome] = None
    verification: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    structured_error: Optional[StructuredMathError] = None
    graph_data: list[dict] = field(default_factory=list)
