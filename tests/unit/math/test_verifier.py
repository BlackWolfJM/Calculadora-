import sympy

from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.verification import MathVerifier


def test_verify_derivative():
    verifier = MathVerifier()
    x = sympy.Symbol("x")
    original = x**2

    # Correct calculation: d/dx(x^2) = 2*x
    assert verifier.verify_derivative(original, x, "2*x") is True

    # Incorrect calculation
    assert verifier.verify_derivative(original, x, "5*x") is False


def test_verify_integral():
    verifier = MathVerifier()
    x = sympy.Symbol("x")
    original = 3 * x**2

    # Correct antiderivative: x^3
    assert verifier.verify_integral(original, x, "x**3") is True

    # Correct with constant: x^3 + 5
    assert verifier.verify_integral(original, x, "x**3 + 5") is True

    # Incorrect antiderivative
    assert verifier.verify_integral(original, x, "x**4") is False


def test_attach_verification():
    verifier = MathVerifier()
    x = sympy.Symbol("x", real=True)
    original = x**2

    response = SolutionResponse(
        response_id="123",
        status=ResolutionStatus.SUCCESS,
        calculation=CalculationBlock(
            status="SUCCESS",
            primary_result=ResultItem(
                value=MathPayload(canonical_text="2*x", latex="2 x"), label="Derivada"
            ),
        ),
    )

    verified_response = verifier.attach_verification(
        response, original, {"variable": "x", "order": 1}, "derivatives"
    )

    assert "Verificado matemáticamente con éxito." in verified_response.verification
    assert verified_response.status == ResolutionStatus.SUCCESS

    # Now with bad result
    response_bad = SolutionResponse(
        response_id="123",
        status=ResolutionStatus.SUCCESS,
        calculation=CalculationBlock(
            status="SUCCESS",
            primary_result=ResultItem(
                value=MathPayload(canonical_text="5*x", latex="5 x"), label="Derivada"
            ),
        ),
    )

    verified_bad = verifier.attach_verification(
        response_bad, original, {"variable": "x", "order": 1}, "derivatives"
    )
    assert "No se pudo verificar" in verified_bad.verification
    assert verified_bad.status == ResolutionStatus.SUCCESS_WITH_WARNINGS
    assert any("No se pudo verificar" in w for w in verified_bad.warnings)
