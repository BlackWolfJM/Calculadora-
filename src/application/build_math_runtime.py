from src.application.solve_expression import SolveExpressionUseCase
from src.domain.modules.derivatives.module import DerivativesModule
from src.domain.modules.derivatives.steps import DerivativeStepGenerator
from src.domain.modules.equations.module import EquationsModule
from src.domain.modules.integrals.module import IntegralsModule
from src.domain.modules.matrices import MatrixModule
from src.domain.modules.multivariable.module import MultivariableModule
from src.domain.modules.structured import OPERATIONS, StructuredModule
from src.domain.registry import ModuleRegistry
from src.domain.verification import MathVerifier
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def build_math_runtime() -> SolveExpressionUseCase:
    """
    Construye de manera aislada el motor matemático completo.
    Diseñado para ser invocado dentro de procesos hijos de multiprocessing
    sin depender de interfaces de usuario (PySide6) ni base de datos local (SQLite).
    """
    parser = MathParser()
    adapter = SympyAdapter()
    step_generator = DerivativeStepGenerator(adapter)

    registry = ModuleRegistry()
    registry.register(DerivativesModule(adapter))
    registry.register(IntegralsModule(adapter))
    registry.register(EquationsModule(adapter))
    registry.register(MultivariableModule(adapter, step_generator))
    registry.register(MatrixModule())
    for module_id in OPERATIONS:
        registry.register(StructuredModule(module_id, adapter))

    verifier = MathVerifier(adapter)

    return SolveExpressionUseCase(parser, registry, verifier)
