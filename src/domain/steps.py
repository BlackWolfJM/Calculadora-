from dataclasses import dataclass, field
from enum import Enum
from typing import List


class StepCoverage(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class StepStatus(Enum):
    SUCCESS = "success"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class EducationalStep:
    """Representa un único paso educativo con su transformación."""

    step_id: str
    rule_name: str
    explanation: str
    before_latex: str
    after_latex: str
    sub_steps: List["EducationalStep"] = field(default_factory=list)


@dataclass(frozen=True)
class StepOutcome:
    """Resultado del motor de pasos para un problema completo."""

    status: StepStatus
    coverage: StepCoverage
    steps: List[EducationalStep]
