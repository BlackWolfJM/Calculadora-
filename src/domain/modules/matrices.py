"""Álgebra lineal exacta y procedimientos del espacio de matrices."""

import ast
import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.matrices.exceptions import MatrixError

from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.steps import EducationalStep, StepCoverage, StepOutcome, StepStatus
from src.infrastructure.parsing.matrix_parser import (
    MatrixEvaluator,
    MatrixInput,
    as_matrix,
    matrix_power,
    matrix_symbols,
    parse_matrix_input,
)

VERIFIED = "Verificado matemáticamente con éxito."


def _tex(value):
    return sp.latex(value, mat_delim="[", mat_str="matrix")


def _canonical(value) -> str:
    if not isinstance(value, sp.MatrixBase):
        return str(value)
    return re.sub(
        r"\b(I|E|Abs)\b",
        lambda match: {"I": "i", "E": "e", "Abs": "abs"}[match[0]],
        str(value.tolist()),
    )


def _step(identifier, title, explanation, before, after) -> EducationalStep:
    return EducationalStep(identifier, title, explanation, before, after)


@dataclass
class MatrixResult:
    value: object
    steps: list[EducationalStep]
    verified: bool = False
    named: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _one(value, rule, formula, explanation, verified=False) -> MatrixResult:
    return MatrixResult(
        value, [_step("method", rule, explanation, formula, _tex(value))], verified
    )


def _many(named, rule, formula, explanation, verified=False) -> MatrixResult:
    result = _one(sp.Tuple(*named.values()), rule, formula, explanation, verified)
    result.named = named
    return result


def _square(matrix):
    if matrix.rows != matrix.cols:
        raise ValueError("Esta operación requiere una matriz cuadrada.")
    return matrix


def _spectral(matrix):
    if max(matrix.shape) > 5:
        raise ValueError("Este cálculo espectral admite matrices de hasta 5 × 5.")
    return matrix


def _pair(value):
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("Introduce dos operandos en la forma [A, B].")
    return value


def _same(left, right) -> bool:
    return left.shape == right.shape and all(
        sp.simplify(entry) == 0 for entry in left - right
    )


def _nonzero(entry):
    return entry.is_zero is not True


def _eliminate(matrix, column_count, reduced):
    """Reducción por filas con las mismas operaciones que se muestran al usuario."""
    work = matrix.as_mutable()
    pivot_row = 0
    pivots = []
    steps = []
    multiplier = sp.S.One

    def record(title, explanation, before):
        steps.append(
            _step(f"row-{len(steps) + 1}", title, explanation, _tex(before), _tex(work))
        )

    for column in range(column_count):
        candidates = [
            row for row in range(pivot_row, work.rows) if _nonzero(work[row, column])
        ]
        if not candidates:
            continue
        pivot = next(
            (row for row in candidates if work[row, column].is_zero is False),
            candidates[0],
        )
        if pivot != pivot_row:
            before = work.copy()
            work.row_swap(pivot, pivot_row)
            multiplier = -multiplier
            record(
                "Intercambio de filas",
                f"Intercambia F{pivot + 1} y F{pivot_row + 1}.",
                before,
            )
        divisor = work[pivot_row, column]
        if reduced and divisor != 1:
            before = work.copy()
            work.row_op(pivot_row, lambda value, _: sp.cancel(value / divisor))
            record(
                "Normalización del pivote",
                rf"Divide la fila F{pivot_row + 1} entre \({_tex(divisor)}\).",
                before,
            )
            divisor = sp.S.One
        before = work.copy()
        descriptions = []
        for row in range(0 if reduced else pivot_row + 1, work.rows):
            if row == pivot_row or not _nonzero(work[row, column]):
                continue
            factor = sp.cancel(work[row, column] / divisor)
            work.row_op(
                row,
                lambda value, index: sp.cancel(value - factor * work[pivot_row, index]),
            )
            descriptions.append(
                rf"\(F_{{{row + 1}}}\gets F_{{{row + 1}}}"
                rf"-\left({_tex(factor)}\right)F_{{{pivot_row + 1}}}\)"
            )
        if descriptions:
            record("Eliminación por filas", ", ".join(descriptions) + ".", before)
        pivots.append(column)
        pivot_row += 1
        if pivot_row == work.rows:
            break
    return work.as_immutable(), pivots, steps, multiplier


def _determinant(matrix, method="auto", index=1):
    matrix = _square(matrix)
    if method in {"row", "column"}:
        if not isinstance(index, int) or not 1 <= index <= matrix.rows:
            raise ValueError("Selecciona una fila o columna dentro de la matriz.")
        axis = index - 1
        coords = (
            [(axis, column) for column in range(matrix.cols)]
            if method == "row"
            else [(row, axis) for row in range(matrix.rows)]
        )
        terms = [
            (matrix[row, column], matrix.cofactor(row, column))
            for row, column in coords
        ]
        result = sp.simplify(sum(entry * cofactor for entry, cofactor in terms))
        formula = r"+".join(
            rf"\left({_tex(entry)}\right)\left({_tex(cofactor)}\right)"
            for entry, cofactor in terms
        )
        return _one(
            result,
            "Expansión por cofactores",
            formula,
            "Multiplica las entradas de la línea seleccionada por sus cofactores.",
            sp.simplify(result - matrix.det()) == 0,
        )
    if method == "elimination":
        triangular, _, steps, sign = _eliminate(matrix, matrix.cols, False)
        result = sp.simplify(sign * sp.prod(triangular.diagonal()))
        steps.append(
            _step(
                "diagonal",
                "Producto de la diagonal",
                "Multiplica la diagonal y cambia el signo por cada intercambio.",
                rf"\left({_tex(sign)}\right)\prod_i u_{{ii}}",
                _tex(result),
            )
        )
        return MatrixResult(result, steps, sp.simplify(result - matrix.det()) == 0)
    return _one(
        matrix.det(),
        "Determinante",
        r"\det A",
        "El determinante es el factor de escala orientado asociado con la matriz.",
    )


def _inverse(matrix):
    matrix = _square(matrix)
    result = matrix.inv()
    return _one(
        result,
        "Matriz inversa",
        r"A^{-1}",
        "Calcula la inversa y comprueba que el producto dé la identidad.",
        _same(matrix * result, sp.eye(matrix.rows)),
    )


def _matrix_binary(value, operation):
    left, right = map(as_matrix, _pair(value))
    if operation == "product":
        if left.cols != right.rows:
            raise ValueError("Las columnas de A deben coincidir con las filas de B.")
        return _one(
            left * right,
            "Producto de matrices",
            r"(AB)_{ij}=\sum_k A_{ik}B_{kj}",
            "Multiplica cada fila de A por cada columna de B.",
        )
    if left.shape != right.shape:
        raise ValueError("Las dos matrices deben tener las mismas dimensiones.")
    add = operation == "add"
    sign = "+" if add else "-"
    return _one(
        left + right if add else left - right,
        "Suma de matrices" if add else "Resta de matrices",
        rf"(A{sign}B)_{{ij}}=A_{{ij}}{sign}B_{{ij}}",
        "Opera las entradas que ocupan la misma posición.",
    )


def _linear_system(left, right, method="gauss"):
    if left.rows != right.rows:
        raise ValueError("A y B deben tener el mismo número de filas.")
    if method == "inverse":
        result = _square(left).inv() * right
        return _one(
            result,
            "Método de la inversa",
            r"X=A^{-1}B",
            "Multiplica ambos lados por la inversa.",
            _same(left * result, right),
        )
    if method == "cramer":
        _square(left)
        determinant = left.det()
        if determinant.is_zero is True:
            raise ValueError("Cramer requiere un determinante distinto de cero.")
        values = []
        for column in range(right.cols):
            solution = []
            for index in range(left.cols):
                replaced = left.as_mutable()
                replaced[:, index] = right[:, column]
                solution.append(sp.cancel(replaced.det() / determinant))
            values.append(solution)
        result = sp.ImmutableMatrix(values).T
        return _one(
            result,
            "Regla de Cramer",
            r"x_i=\frac{\det(A_i)}{\det A}",
            "Sustituye una columna de A por el término independiente.",
            _same(left * result, right),
        )
    augmented = left.row_join(right)
    echelon, pivots, steps, _ = _eliminate(augmented, augmented.cols, True)
    coefficient_pivots = tuple(pivot for pivot in pivots if pivot < left.cols)
    rank = len(coefficient_pivots)
    augmented_rank = len(pivots)
    statement = (
        rf"\operatorname{{rg}}(A)={rank},\quad "
        rf"\operatorname{{rg}}([A|B])={augmented_rank}"
    )
    if rank != augmented_rank:
        label = "Sin solución"
    elif rank == left.cols:
        label = "Solución única"
    else:
        label = "Infinitas soluciones"
    steps.append(
        _step(
            "compatibility",
            "Teorema de Rouché–Frobenius",
            f"{label}. Comparamos los rangos y el número de incógnitas ({left.cols}).",
            statement,
            rf"\text{{{label}}}",
        )
    )
    if method == "compatibility" or rank != augmented_rank:
        return MatrixResult(label, steps)
    free = [column for column in range(left.cols) if column not in coefficient_pivots]
    values = sp.zeros(left.cols, right.cols)
    taken_names = {str(symbol) for symbol in augmented.free_symbols}
    for column in range(right.cols):
        for index in free:
            name = f"t_{index + 1}_{column + 1}"
            while name in taken_names:
                name += "_"
            values[index, column] = sp.Symbol(name)
        for row, pivot in enumerate(coefficient_pivots):
            values[pivot, column] = sp.simplify(
                echelon[row, left.cols + column]
                - sum(echelon[row, index] * values[index, column] for index in free)
            )
    result = values.as_immutable()
    return MatrixResult(result, steps, _same(left * result, right))


def _decompose(matrix, operation):
    if operation == "lu":
        lower, upper, swaps = matrix.LUdecomposition()
        permutation = sp.eye(matrix.rows)
        for first, second in swaps:
            permutation.row_swap(first, second)
        return _many(
            {"P": permutation, "L": lower, "U": upper},
            "Factorización LU",
            r"PA=LU",
            "Aplica pivoteo por filas y separa los factores.",
            _same(permutation * matrix, lower * upper),
        )
    if operation == "cholesky":
        matrix = _square(matrix)
        lower = matrix.cholesky(hermitian=True)
        return _many(
            {"L": lower, "L^{*}": lower.H},
            "Factorización de Cholesky",
            r"A=LL^{*}",
            "Factoriza la matriz hermítica definida positiva.",
            _same(matrix, lower * lower.H),
        )
    if operation == "svd":
        left, values, right = _spectral(matrix).singular_value_decomposition()
        return _many(
            {"U": left, r"\Sigma": values, "V": right},
            "SVD reducida",
            r"A=U\Sigma V^{*}",
            "Los valores singulares se obtienen de A* A.",
            _same(matrix, left * values * right.H),
        )
    matrix = _spectral(_square(matrix))
    if operation == "jordan":
        transform, jordan = matrix.jordan_form()
        return _many(
            {"P": transform, "J": jordan},
            "Forma de Jordan",
            r"AP=PJ",
            "Agrupa cadenas de vectores propios generalizados.",
            _same(matrix * transform, transform * jordan),
        )
    transform, diagonal = matrix.diagonalize()
    return _many(
        {"P": transform, "D": diagonal},
        "Diagonalización",
        r"AP=PD",
        "Forma una base de vectores propios y ordena sus valores en la diagonal.",
        _same(matrix * transform, transform * diagonal),
    )


def _eigen(matrix):
    matrix = _spectral(_square(matrix))
    values = matrix.eigenvects()
    named = {r"p(\lambda)": matrix.charpoly(sp.Symbol("lambda")).as_expr()}
    valid = bool(values) and sum(item[1] for item in values) == matrix.rows
    for index, (value, multiplicity, vectors) in enumerate(values, 1):
        named[rf"\lambda_{{{index}}}"] = value
        named[rf"m_{{{index}}}"] = multiplicity
        for offset, vector in enumerate(vectors, 1):
            named[rf"v_{{{index},{offset}}}"] = vector
            valid = valid and _same(matrix * vector, value * vector)
    return _many(
        named,
        "Valores y vectores propios",
        r"\det(\lambda I-A)=0",
        "Halla las raíces y una base del núcleo para cada valor propio.",
        valid,
    )


def _matrix_expression(value, parameters):
    environment = {}
    for name in ("A", "B"):
        source = parameters.get(name, "")
        if source:
            if not isinstance(source, str):
                raise ValueError(f"La matriz {name} debe introducirse como texto.")
            environment[name] = as_matrix(
                MatrixEvaluator(parse_matrix_input(source)).evaluate()
            )
    evaluator = MatrixEvaluator(value, environment)
    tree = value.tree
    if (
        isinstance(tree, ast.Compare)
        and len(tree.ops) == 1
        and isinstance(tree.ops[0], ast.Eq)
    ):
        left, right = tree.left, tree.comparators[0]

        def unknown(node):
            return isinstance(node, ast.Name) and node.id in {"X", "Y"}

        if unknown(left) or unknown(right):
            answer = as_matrix(evaluator.evaluate(right if unknown(left) else left))
            return _one(
                answer,
                "Igualdad matricial",
                r"X=A",
                "La incógnita toma el valor del otro miembro de la ecuación.",
            )
        if any(unknown(node) for node in ast.walk(right)) and not any(
            unknown(node) for node in ast.walk(left)
        ):
            left, right = right, left

        if isinstance(left, ast.BinOp) and unknown(left.right) != unknown(left.left):
            on_right = unknown(left.right)
            known = as_matrix(evaluator.evaluate(left.left if on_right else left.right))
            target = as_matrix(evaluator.evaluate(right))
            if isinstance(left.op, ast.Mult):
                if on_right:
                    return _linear_system(known, target)
                result = _linear_system(known.T, target.T)
                if isinstance(result.value, sp.MatrixBase):
                    result.value = result.value.T
                return result
            if isinstance(left.op, ast.Add):
                answer = target - known
            elif isinstance(left.op, ast.Sub):
                answer = known - target if on_right else target + known
            else:
                raise ValueError(
                    "Usa una ecuación lineal con una sola matriz incógnita."
                )
            return _one(
                answer,
                "Despeje matricial",
                r"X=\text{términos conocidos}",
                "Agrupa los términos conocidos en el lado opuesto.",
            )
    if isinstance(tree, ast.Tuple) and all(
        isinstance(item, ast.Compare) for item in tree.elts
    ):
        named = {}
        steps = []
        verified = True
        for index, equation in enumerate(tree.elts, 1):
            result = _matrix_expression(MatrixInput(value.source, equation), parameters)
            named[f"R_{{{index}}}"] = result.value
            steps.extend(result.steps)
            verified = verified and result.verified
        return MatrixResult(sp.Tuple(*named.values()), steps, verified, named)
    result = evaluator.evaluate()
    if isinstance(result, tuple):
        result = as_matrix(result)
    if result in (sp.true, sp.false):
        result = "Verdadero" if result is sp.true else "Falso"
    return _one(
        result,
        "Expresión matricial",
        r"\text{Expresión introducida}",
        "Evalúa primero las funciones, potencias y productos indicados.",
    )


def _run(operation, value, parameters):
    if operation == "expression":
        return _matrix_expression(value, parameters)
    operand = MatrixEvaluator(value).evaluate()
    if operation in {"product", "add", "subtract"}:
        return _matrix_binary(operand, operation)
    if operation in {"gauss", "inverse_system", "cramer", "compatibility"}:
        method = "inverse" if operation == "inverse_system" else operation
        return _linear_system(*map(as_matrix, _pair(operand)), method)
    if operation in {"scale", "power"}:
        matrix, scalar = _pair(operand)
        matrix = as_matrix(matrix)
        if operation == "power":
            return _one(
                matrix_power(matrix, scalar),
                "Potencia de una matriz",
                r"A^{p}",
                "Evalúa la potencia según el exponente elegido.",
            )
        if not isinstance(scalar, sp.Expr) or scalar.is_finite is False:
            raise ValueError(
                "El factor de escala debe ser una expresión escalar finita."
            )
        return _one(
            matrix * scalar,
            "Producto por un escalar",
            r"(cA)_{ij}=c\,a_{ij}",
            "Multiplica cada entrada por el factor.",
        )
    matrix = as_matrix(operand)
    if operation == "determinant":
        return _determinant(
            matrix, parameters.get("method", "auto"), parameters.get("index", 1)
        )
    if operation == "inverse":
        return _inverse(matrix)
    if operation in {"lu", "cholesky", "svd", "jordan", "diagonalize"}:
        return _decompose(matrix, operation)
    if operation == "eigen":
        return _eigen(matrix)
    if operation in {"echelon", "rref", "rank"}:
        echelon, pivots, steps, _ = _eliminate(matrix, matrix.cols, operation == "rref")
        if operation == "rank":
            result = sp.Integer(len(pivots))
            steps.append(
                _step(
                    "pivots",
                    "Rango",
                    "Cuenta los pivotes de la forma escalonada.",
                    _tex(echelon),
                    _tex(result),
                )
            )
        else:
            result = echelon
            if not steps:
                steps.append(
                    _step(
                        "already",
                        "Forma escalonada",
                        "La matriz ya tiene la forma solicitada.",
                        _tex(matrix),
                        _tex(result),
                    )
                )
        return MatrixResult(result, steps)
    value_and_rule = {
        "transpose": (
            lambda: matrix.T,
            "Transpuesta",
            r"(A^{T})_{ij}=A_{ji}",
            "Intercambia filas y columnas.",
        ),
        "trace": (
            lambda: _square(matrix).trace(),
            "Traza",
            r"\operatorname{tr}(A)=\sum_i a_{ii}",
            "Suma las entradas de la diagonal.",
        ),
        "adjugate": (
            lambda: _square(matrix).adjugate(),
            "Adjunta",
            r"\operatorname{adj}(A)=C^{T}",
            "Transpone la matriz de cofactores.",
        ),
        "pseudoinverse": (
            matrix.pinv,
            "Pseudoinversa",
            r"A^{+}",
            "Calcula la pseudoinversa de Moore–Penrose.",
        ),
        "exponential": (
            lambda: _spectral(_square(matrix)).exp(),
            "Exponencial matricial",
            r"e^A=\sum_{k=0}^{\infty}\frac{A^k}{k!}",
            "Evalúa la exponencial mediante la estructura espectral.",
        ),
    }[operation]
    calculate, rule, formula, explanation = value_and_rule
    return _one(calculate(), rule, formula, explanation)


OPERATIONS = frozenset(
    {
        "determinant",
        "inverse",
        "transpose",
        "rank",
        "scale",
        "echelon",
        "rref",
        "diagonalize",
        "power",
        "lu",
        "cholesky",
        "add",
        "subtract",
        "product",
        "expression",
        "gauss",
        "inverse_system",
        "cramer",
        "compatibility",
        "eigen",
        "jordan",
        "exponential",
        "svd",
        "adjugate",
        "pseudoinverse",
        "trace",
    }
)


class MatrixModule:
    def get_id(self) -> str:
        return "matrices"

    def solve(self, value: MatrixInput, parameters: dict) -> SolutionResponse:
        operation = parameters.get("operation", "determinant")
        if not isinstance(operation, str) or operation not in OPERATIONS:
            return SolutionResponse(
                "",
                ResolutionStatus.UNSUPPORTED,
                error="Operación matricial no disponible.",
            )
        try:
            result = _run(operation, value, parameters)
        except (MatrixError, NotImplementedError, TypeError, ZeroDivisionError) as exc:
            raise ValueError(
                "La operación no está definida para estas matrices o sus dimensiones."
            ) from exc
        approximate = parameters.get("precision")
        if approximate is not None and (
            type(approximate) is not int or not 2 <= approximate <= 15
        ):
            raise ValueError(
                "La precisión debe estar entre 2 y 15 cifras significativas."
            )

        def display(value):
            if approximate is None:
                return _tex(value)
            if isinstance(value, sp.MatrixBase):
                return _tex(value.applyfunc(lambda entry: entry.evalf(approximate)))
            if isinstance(value, sp.Expr):
                return _tex(value.evalf(approximate))
            return _tex(value)

        warnings = result.warnings
        if operation in {
            "inverse",
            "gauss",
            "inverse_system",
            "cramer",
            "lu",
            "rank",
            "echelon",
            "rref",
            "compatibility",
            "expression",
            "pseudoinverse",
            "determinant",
        } and (
            matrix_symbols(value)
            or any(
                matrix_symbols(parse_matrix_input(parameters[name]))
                for name in ("A", "B")
                if operation == "expression" and parameters.get(name)
            )
        ):
            warnings.append(
                "Con parámetros libres, las conclusiones valen donde los pivotes "
                "y denominadores utilizados son distintos de cero."
            )
        related = [
            ResultItem(MathPayload(_canonical(item), display(item)), label)
            for label, item in result.named.items()
        ]
        if related:
            canonical = "\n".join(
                f"{item.label} = {item.value.canonical_text}" for item in related
            )
            latex = (
                r"\begin{aligned}"
                + r"\\".join(f"{item.label}&={item.value.latex}" for item in related)
                + r"\end{aligned}"
            )
        else:
            canonical, latex = _canonical(result.value), display(result.value)
        status = (
            ResolutionStatus.SUCCESS_WITH_WARNINGS
            if warnings
            else ResolutionStatus.SUCCESS
        )
        return SolutionResponse(
            "",
            status,
            calculation=CalculationBlock(
                status.value,
                ResultItem(MathPayload(canonical, latex), "Resultado"),
                related,
            ),
            procedure=StepOutcome(
                StepStatus.SUCCESS, StepCoverage.COMPLETE, result.steps
            ),
            verification=VERIFIED if result.verified else None,
            warnings=warnings,
        )
