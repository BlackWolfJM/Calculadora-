import uuid
from dataclasses import dataclass
from enum import Enum

from src.domain.expressions.ast_nodes import ExpressionNode
from src.domain.modules.multivariable.operations import (
    solve_directional,
    solve_gradient,
    solve_laplacian,
    solve_multivariable_value,
    solve_partial,
)
from src.domain.responses import ResolutionStatus, SolutionResponse


@dataclass(frozen=True)
class ParameterDescriptor:
    name: str
    type: str


@dataclass(frozen=True)
class OperationDescriptor:
    operation_id: str
    display_name_key: str
    input_kind: str
    parameters: tuple[ParameterDescriptor, ...]
    supports_steps: bool
    supports_verification: bool
    supports_plot: bool


class ModuleStatus(Enum):
    PLANNED = "planned"
    EXPERIMENTAL = "experimental"
    LIMITED = "limited"
    STABLE = "stable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ModuleCapabilities:
    exact_result: bool
    numeric_result: bool
    full_steps: bool
    partial_steps: bool
    symbolic_verification: bool
    numeric_verification: bool
    domain_conditions: bool
    plot_data: bool
    specific_export: bool
    point_evaluation: bool


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    display_name_key: str
    description_key: str
    category: str
    status: ModuleStatus
    operations: tuple[OperationDescriptor, ...]
    capabilities: ModuleCapabilities
    schema_version: int


class MultivariableModule:
    """Módulo para operaciones escalares de cálculo multivariable (Fase A)."""

    def __init__(self, adapter, derivative_steps):
        self.adapter = adapter
        self.derivative_steps = derivative_steps
        self._descriptor = ModuleDescriptor(
            module_id="multivariable",
            display_name_key="module.multivariable.name",
            description_key="module.multivariable.desc",
            category="calculus",
            status=ModuleStatus.EXPERIMENTAL,
            operations=(
                OperationDescriptor(
                    operation_id="multivariable_value",
                    display_name_key="op.multivariable.value",
                    input_kind="expression",
                    parameters=(
                        ParameterDescriptor("variables", "List[str]"),
                        ParameterDescriptor("point", "Dict[str, float]"),
                    ),
                    supports_steps=True,
                    supports_verification=True,
                    supports_plot=False,
                ),
                OperationDescriptor(
                    operation_id="partial",
                    display_name_key="op.multivariable.partial",
                    input_kind="expression",
                    parameters=(
                        ParameterDescriptor("variable", "str"),
                        ParameterDescriptor("order", "int"),
                    ),
                    supports_steps=True,
                    supports_verification=True,
                    supports_plot=False,
                ),
                OperationDescriptor(
                    operation_id="gradient",
                    display_name_key="op.multivariable.gradient",
                    input_kind="expression",
                    parameters=(ParameterDescriptor("variables", "List[str]"),),
                    supports_steps=True,
                    supports_verification=True,
                    supports_plot=False,
                ),
                OperationDescriptor(
                    operation_id="directional",
                    display_name_key="op.multivariable.directional",
                    input_kind="expression",
                    parameters=(
                        ParameterDescriptor("variables", "List[str]"),
                        ParameterDescriptor("point", "Dict[str, float]"),
                        ParameterDescriptor("direction", "List[float]"),
                    ),
                    supports_steps=True,
                    supports_verification=True,
                    supports_plot=False,
                ),
                OperationDescriptor(
                    operation_id="laplacian",
                    display_name_key="op.multivariable.laplacian",
                    input_kind="expression",
                    parameters=(ParameterDescriptor("variables", "List[str]"),),
                    supports_steps=True,
                    supports_verification=True,
                    supports_plot=False,
                ),
            ),
            capabilities=ModuleCapabilities(
                exact_result=True,
                numeric_result=True,
                full_steps=True,
                partial_steps=True,
                symbolic_verification=True,
                numeric_verification=False,
                domain_conditions=False,
                plot_data=False,
                specific_export=False,
                point_evaluation=True,
            ),
            schema_version=1,
        )
        self.handlers = {
            "multivariable_value": lambda expr, params: solve_multivariable_value(
                expr, params, self.adapter
            ),
            "partial": lambda expr, params: solve_partial(
                expr, params, self.adapter, self.derivative_steps
            ),
            "gradient": lambda expr, params: solve_gradient(
                expr, params, self.adapter, self.derivative_steps
            ),
            "directional": lambda expr, params: solve_directional(
                expr, params, self.adapter, self.derivative_steps
            ),
            "laplacian": lambda expr, params: solve_laplacian(
                expr, params, self.adapter, self.derivative_steps
            ),
        }

    @property
    def descriptor(self) -> ModuleDescriptor:
        return self._descriptor

    def get_id(self) -> str:
        return self._descriptor.module_id

    def solve(self, expression: ExpressionNode, parameters: dict) -> SolutionResponse:
        operation = parameters.get("operation")
        handler = self.handlers.get(operation) if isinstance(operation, str) else None

        if handler is None:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.UNSUPPORTED,
                error="Operación de cálculo multivariable no soportada o ausente.",
            )

        try:
            return handler(expression, parameters)
        except ValueError as exc:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.INVALID_INPUT,
                error=str(exc),
            )
        except NotImplementedError:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.UNSUPPORTED,
                error="La operación aún no está disponible.",
            )
        except Exception:
            return SolutionResponse(
                response_id=str(uuid.uuid4()),
                status=ResolutionStatus.FAILED,
                error="Ocurrió un error interno durante el cálculo multivariable.",
            )
