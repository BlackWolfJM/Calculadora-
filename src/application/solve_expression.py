import uuid
from typing import Any, Dict

from src.domain.errors import StructuredMathError
from src.domain.modules.matrices import MatrixModule
from src.domain.modules.structured import StructuredModule
from src.domain.registry import ModuleRegistry
from src.domain.responses import ResolutionStatus, SolutionResponse
from src.domain.verification import MathVerifier
from src.infrastructure.parsing.matrix_parser import parse_matrix_input
from src.infrastructure.parsing.normalizer import MathNormalizer
from src.infrastructure.parsing.parser import MathParser


class SolveExpressionUseCase:
    """
    Coordinador central que aísla la lógica de negocio de la interfaz.
    Se encarga de orquestar el flujo:
    Parseo -> Selección de Módulo -> Resolución -> Respuesta.
    """

    def __init__(
        self, parser: MathParser, registry: ModuleRegistry, verifier: "MathVerifier"
    ):
        self.parser = parser
        self.registry = registry
        self.verifier = verifier
        self.normalizer = MathNormalizer()

    def execute(
        self, expression: str, module_id: str, parameters: Dict[str, Any]
    ) -> SolutionResponse:
        response_id = str(uuid.uuid4())
        normalized_expr = None

        try:
            # 1. Normalización explícita para adjuntarla en la respuesta
            normalized_expr = self.normalizer.normalize(expression)

            # 2. Selección de módulo y validación de la sintaxis correspondiente
            module = self.registry.get_module(module_id)
            if isinstance(module, MatrixModule):
                ast = parse_matrix_input(expression)
                normalized_expr = ast.source
            elif isinstance(module, StructuredModule):
                ast = self.parser.parse(expression, structured=True)
            else:
                ast = self.parser.parse(expression)

            if not module:
                return SolutionResponse(
                    response_id=response_id,
                    status=ResolutionStatus.UNSUPPORTED,
                    normalized_input=normalized_expr,
                    error=f"Módulo '{module_id}' no encontrado o no soportado.",
                )

            # 4. Cálculo e invocación
            response = module.solve(ast, parameters)

            # 5. Adjuntar entrada normalizada
            from dataclasses import replace

            response = replace(
                response, response_id=response_id, normalized_input=normalized_expr
            )

            # 6. Verificación independiente
            try:
                response = self.verifier.verify_ast(
                    response, ast, parameters, module_id
                )
            except Exception:
                warning = "Verificación no disponible por un fallo interno."
                response = replace(
                    response,
                    verification=None,
                    warnings=[*response.warnings, warning],
                    status=ResolutionStatus.SUCCESS_WITH_WARNINGS
                    if response.status is ResolutionStatus.SUCCESS
                    else response.status,
                )

            return response

        except StructuredMathError as e:
            return SolutionResponse(
                response_id=response_id,
                status=ResolutionStatus.INVALID_INPUT,
                normalized_input=normalized_expr,
                error=e.message,
                structured_error=e,
            )
        except ValueError as e:
            # Errores predecibles de validación, límites, o parsing
            return SolutionResponse(
                response_id=response_id,
                status=ResolutionStatus.INVALID_INPUT,
                normalized_input=normalized_expr,
                error=str(e),
            )
        except Exception:
            # Cualquier otro fallo interno inesperado
            return SolutionResponse(
                response_id=response_id,
                status=ResolutionStatus.FAILED,
                normalized_input=normalized_expr,
                error="Ocurrió un error interno durante el cálculo.",
            )
