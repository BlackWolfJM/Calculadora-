from src.application.solve_expression import SolveExpressionUseCase
from src.domain.modules.protocol import MathModule
from src.domain.registry import ModuleRegistry
from src.domain.responses import ResolutionStatus, SolutionResponse
from src.domain.verification import MathVerifier
from src.infrastructure.parsing.parser import MathParser


class DummyModule(MathModule):
    def get_id(self) -> str:
        return "dummy"

    def solve(self, expression, parameters):
        return SolutionResponse(response_id="test", status=ResolutionStatus.SUCCESS)


class ThrowingModule(MathModule):
    def get_id(self) -> str:
        return "thrower"

    def solve(self, expression, parameters):
        raise RuntimeError("Unexpected error")


def test_solve_expression_success():
    parser = MathParser()
    registry = ModuleRegistry()
    registry.register(DummyModule())
    verifier = MathVerifier()

    use_case = SolveExpressionUseCase(parser, registry, verifier)
    response = use_case.execute("2x", "dummy", {})

    assert response.status == ResolutionStatus.SUCCESS
    assert response.normalized_input == "2*x"


def test_solve_expression_unsupported_module():
    parser = MathParser()
    registry = ModuleRegistry()
    verifier = MathVerifier()

    use_case = SolveExpressionUseCase(parser, registry, verifier)
    response = use_case.execute("2x", "missing", {})

    assert response.status == ResolutionStatus.UNSUPPORTED
    assert response.normalized_input == "2*x"


def test_solve_expression_invalid_input():
    parser = MathParser()
    registry = ModuleRegistry()
    verifier = MathVerifier()

    use_case = SolveExpressionUseCase(parser, registry, verifier)
    # Parser debería arrojar ValueError porque está vacío
    response = use_case.execute("", "dummy", {})

    assert response.status == ResolutionStatus.INVALID_INPUT


def test_solve_expression_module_exception_handled():
    parser = MathParser()
    registry = ModuleRegistry()
    registry.register(ThrowingModule())
    verifier = MathVerifier()

    use_case = SolveExpressionUseCase(parser, registry, verifier)
    response = use_case.execute("x", "thrower", {})

    assert response.status == ResolutionStatus.FAILED
    assert "error interno" in response.error
