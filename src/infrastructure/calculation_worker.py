import dataclasses
from multiprocessing.connection import Connection

from src.application.build_math_runtime import build_math_runtime
from src.domain.errors import StructuredMathError
from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.steps import EducationalStep, StepCoverage, StepOutcome, StepStatus


def serialize_response(resp: SolutionResponse) -> dict:
    """Convierte la respuesta en un diccionario para el proceso de presentación."""

    def as_dict(obj):
        if obj is None:
            return None
        if isinstance(obj, (ResolutionStatus, StepStatus, StepCoverage)):
            return obj.value
        if isinstance(obj, StructuredMathError):
            return {
                "code": obj.code,
                "message": obj.message,
                "line": obj.line,
                "column": obj.column,
                "end_line": obj.end_line,
                "end_column": obj.end_column,
                "fragment": obj.fragment,
                "suggestion": obj.suggestion,
                "internal_cause": obj.internal_cause,
            }
        if dataclasses.is_dataclass(obj):
            result = {}
            for f in dataclasses.fields(obj):
                val = getattr(obj, f.name)
                if isinstance(val, list):
                    result[f.name] = [as_dict(i) for i in val]
                elif isinstance(val, tuple):
                    result[f.name] = tuple(as_dict(i) for i in val)
                else:
                    result[f.name] = as_dict(val)
            return result
        return obj

    return as_dict(resp)


def deserialize_response(data: dict) -> SolutionResponse:
    """Convierte diccionario a SolutionResponse reconstruyendo dataclasses."""
    if not isinstance(data, dict):
        return data

    def build_step(d: dict) -> EducationalStep:
        sub_steps = [build_step(s) for s in d.get("sub_steps", [])]
        return EducationalStep(
            step_id=d["step_id"],
            rule_name=d["rule_name"],
            explanation=d["explanation"],
            before_latex=d["before_latex"],
            after_latex=d["after_latex"],
            sub_steps=sub_steps,
        )

    calc = None
    if data.get("calculation"):
        calc_d = data["calculation"]
        def result_item(res_d: dict) -> ResultItem:
            return ResultItem(
                value=MathPayload(
                    canonical_text=res_d["value"]["canonical_text"],
                    latex=res_d["value"]["latex"],
                ),
                label=res_d["label"],
            )

        primary = calc_d.get("primary_result")
        calc = CalculationBlock(
            status=calc_d["status"],
            primary_result=result_item(primary) if primary else None,
            related_results=[
                result_item(item) for item in calc_d.get("related_results", [])
            ],
        )

    proc = None
    if data.get("procedure"):
        proc_d = data["procedure"]
        steps = [build_step(s) for s in proc_d.get("steps", [])]
        proc = StepOutcome(
            status=StepStatus(proc_d["status"]),
            coverage=StepCoverage(proc_d["coverage"]),
            steps=steps,
        )

    status = ResolutionStatus(data["status"])

    struct_error = None
    if data.get("structured_error"):
        se_d = data["structured_error"]
        struct_error = StructuredMathError(
            code=se_d.get("code", ""),
            message=se_d.get("message", ""),
            line=se_d.get("line", 0),
            column=se_d.get("column", 0),
            end_line=se_d.get("end_line", 0),
            end_column=se_d.get("end_column", 0),
            fragment=se_d.get("fragment", ""),
            suggestion=se_d.get("suggestion"),
            internal_cause=se_d.get("internal_cause"),
        )

    return SolutionResponse(
        response_id=data["response_id"],
        status=status,
        normalized_input=data.get("normalized_input"),
        calculation=calc,
        procedure=proc,
        verification=data.get("verification"),
        warnings=data.get("warnings", []),
        error=data.get("error"),
        structured_error=struct_error,
        graph_data=data.get("graph_data", []),
    )


def run_calculation_process(
    request_id: str,
    expression: str,
    module_id: str,
    parameters: dict,
    child_pipe: Connection,
):
    """
    Función pura a nivel de módulo, ejecutada en un proceso separado (spawn).
    """
    try:
        use_case = build_math_runtime()
        response = use_case.execute(expression, module_id, parameters)
        if parameters.get("include_graph", False):
            from src.infrastructure.plotting import build_plot

            try:
                response = dataclasses.replace(
                    response,
                    graph_data=build_plot(expression, module_id, parameters, response),
                )
            except Exception:
                response = dataclasses.replace(
                    response,
                    warnings=[
                        *response.warnings,
                        "La gráfica no está disponible para esta expresión.",
                    ],
                )

        # Forzar response_id al de la request (asegurando un solo ID válido)
        if response.response_id != request_id:
            response = dataclasses.replace(response, response_id=request_id)

        # Enviar respuesta exitosa (serializada)
        child_pipe.send(
            {"schema_version": 1, "success": True, "data": serialize_response(response)}
        )
    except Exception:
        child_pipe.send(
            {
                "schema_version": 1,
                "success": False,
                "request_id": request_id,
                "error_code": "INTERNAL_WORKER_ERROR",
            }
        )
    finally:
        child_pipe.close()
