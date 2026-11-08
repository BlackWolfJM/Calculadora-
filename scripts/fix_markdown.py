import sys
import re

file_path = "20-modulo-calculo-vectorial-reglas-y-codigo.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Module decision
content = content.replace("Se propone un solo identificador de módulo, `vector_calculus`", "Se utilizarán módulos separados (`vectors`, `analytic_geometry` y `multivariable`) para mantener compatibilidad con `07-modulos-matematicos.md`")
content = content.replace("class VectorCalculusModule(MathModule):", "class MultivariableModule(MathModule):\n    # NOTA: También se deben crear VectorsModule y AnalyticGeometryModule separados.")
content = content.replace("def get_id(self) -> str:\n        return \"vector_calculus\"", "def get_id(self) -> str:\n        return \"multivariable\"")

# 2. run_calculation_process signature
content = content.replace("run_calculation_process(req_id, expression, parameters, pipe)", "run_calculation_process(req_id, expression, \"multivariable\", parameters, pipe)")

# 3. IPC envelope validation
old_ipc = """    if not pipe.poll(5.0):
        pytest.fail("Timeout esperando respuesta")
    response = deserialize_response(pipe.recv())"""
new_ipc = """    if not pipe.poll(5.0):
        pytest.fail("Timeout esperando respuesta")
    msg = pipe.recv()
    assert msg.get("schema_version") == 1
    assert msg.get("success") is True
    response = deserialize_response(msg["data"])"""
content = content.replace(old_ipc, new_ipc)

# 4. Define AST nodes completely
old_ast = """@dataclass(frozen=True)
class OperationNode(ExpressionNode):
    name: str
    arguments: tuple[ExpressionNode, ...]"""
new_ast = """@dataclass(frozen=True)
class Region2DNode(ExpressionNode):
    variables: tuple[Symbol, Symbol]
    bounds: tuple[tuple[ExpressionNode, ExpressionNode], ...]

@dataclass(frozen=True)
class Region3DNode(ExpressionNode):
    variables: tuple[Symbol, Symbol, Symbol]
    bounds: tuple[tuple[ExpressionNode, ExpressionNode], ...]

@dataclass(frozen=True)
class DomainNode(ExpressionNode):
    conditions: tuple[ExpressionNode, ...]

@dataclass(frozen=True)
class BoundNode(ExpressionNode):
    lower: ExpressionNode
    upper: ExpressionNode

@dataclass(frozen=True)
class Orientation(ExpressionNode):
    direction: str  # "outward", "inward", "upward", "downward"

@dataclass(frozen=True)
class ClosedSurfaceNode(ExpressionNode):
    components: tuple[ExpressionNode, ...]
    parameters: tuple[Symbol, Symbol]
    bounds: tuple[tuple[ExpressionNode, ExpressionNode], ...]
    orientation: Orientation

@dataclass(frozen=True)
class OperationNode(ExpressionNode):
    name: str
    arguments: tuple[ExpressionNode, ...]"""
content = content.replace(old_ast, new_ast)

# 5. Grammar
grammar_section = """### 0.5.1 Gramática segura para el AST extendido
Para parsear de forma segura, la gramática (Lark) deberá extenderse con producciones inequívocas:
- Vectores: `<x, y, z>`
- Campos: `field(x, y, z; <P, Q, R>)`
- Curvas: `curve(t; <X, Y, Z>; t0, t1)`
- Superficies: `surface(u, v; <X, Y, Z>; u0, u1, v0, v1)`
- Regiones: `region(x, y; x0, x1, y0(x), y1(x))`
- Orientación: `orientation("outward")`
- Superficies cerradas: `closed_surface(u, v; <X, Y, Z>; u0, u1, v0, v1; orientation("outward"))`
"""
if "### 0.5.1 Gramática segura" not in content:
    content = content.replace("### 0.6 Integración con `MathModule`", grammar_section + "\n### 0.6 Integración con `MathModule`")

# 6. Distinguish code clearly
content = content.replace("```python\n# src/domain/", "```python\n# [CÓDIGO QUE REQUIERE AMPLIAR PARSER/AST]\n# src/domain/")
content = content.replace("Código integrable hoy", "[CÓDIGO INTEGRABLE CON ARQUITECTURA ACTUAL]")
content = content.replace("Código listo", "[CÓDIGO QUE REQUIERE AMPLIAR PARSER/AST]")
content = content.replace("ESQUELETO PROPUESTO", "[PSEUDOCÓDIGO ARQUITECTÓNICO]")

# 7. Conservative field INVALID_INPUT -> SUCCESS + explanation
old_conservative = """raise ValueError("El campo vectorial no es conservativo.")"""
new_conservative = """return response("Campo conservativo", sp.sympify(False), [step("check-conserv", "Prueba de campo conservativo", "El rotacional no es cero.", curl, curl)], coverage=StepCoverage.COMPLETE)"""
content = content.replace(old_conservative, new_conservative)

old_cons_test = """assert runtime.potential("y", "-x", variables=["x", "y"]).status is ResolutionStatus.INVALID_INPUT"""
new_cons_test = """r = runtime.potential("y", "-x", variables=["x", "y"])
    assert r.status is ResolutionStatus.SUCCESS
    assert r.calculation.primary_result.value.canonical_text == "False\""""
content = content.replace(old_cons_test, new_cons_test)

# 8. Domain validation PARTIAL
content = content.replace("El dominio multivariable exacto puede quedar como condición simbólica", "El dominio multivariable exacto (COBERTURA: PARTIAL) puede quedar como condición simbólica")

# 9. No Green, Gauss, Stokes yet
content = re.sub(r"(## 15\. Integrales de línea.*?)(?=## 20\.)", "## 15-19. Integrales Avanzadas y Teoremas Vectoriales\n\n**NOTA:** No se implementarán todavía Green, Gauss, Stokes, integrales de línea o integrales de superficie en esta fase.\n\n", content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
