"""Nombres, formatos de entrada y ejemplos de los módulos con listas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    name: str
    instruction: str
    example: str
    input_kind: str = "single"


@dataclass(frozen=True)
class Module:
    title: str
    navigation: str
    icon: str
    operations: dict[str, Operation]


_SQUARE = "[[1, 2], [3, 4]]"
_RECTANGULAR = "[[1, 2, 3], [2, 4, 6]]"
_PAIR = "[[[1, 2], [3, 4]], [[5, 6], [7, 8]]]"
_SYSTEM = "[[[2, 1], [1, -1]], [[5], [1]]]"


MATRIX_OPERATIONS = {
    "determinant": Operation(
        "Determinante", "Introduce una matriz cuadrada A.", _SQUARE
    ),
    "inverse": Operation(
        "Inversa", "Introduce una matriz cuadrada invertible A.", "[[2, 1], [1, 1]]"
    ),
    "product": Operation(
        "Multiplicación A × B",
        "Introduce [A, B].",
        "[[[1, 2], [3, 4]], [[2], [1]]]",
        "binary",
    ),
    "add": Operation(
        "Suma A + B", "Introduce [A, B] con las mismas dimensiones.", _PAIR, "binary"
    ),
    "subtract": Operation(
        "Resta A − B", "Introduce [A, B] con las mismas dimensiones.", _PAIR, "binary"
    ),
    "transpose": Operation(
        "Transpuesta", "Intercambia las filas y columnas de A.", _RECTANGULAR
    ),
    "rank": Operation("Rango", "Cuenta los pivotes de A.", _RECTANGULAR),
    "scale": Operation(
        "Multiplicación por un escalar",
        "Introduce [A, factor].",
        "[[[1, 2], [3, 4]], 1/3]",
        "argument",
    ),
    "power": Operation(
        "Potencia Aᵖ",
        "Introduce [A, exponente]. Usa ∞ para un límite.",
        "[[[4, 0], [0, 9]], 1/2]",
        "argument",
    ),
    "echelon": Operation(
        "Forma escalonada", "Reduce A por filas con pasos.", _RECTANGULAR
    ),
    "rref": Operation(
        "Forma escalonada reducida", "Aplica Gauss–Jordan a A.", _RECTANGULAR
    ),
    "trace": Operation("Traza", "Suma la diagonal de una matriz cuadrada A.", _SQUARE),
    "adjugate": Operation(
        "Adjunta", "Calcula la transpuesta de cofactores de A.", _SQUARE
    ),
    "pseudoinverse": Operation(
        "Pseudoinversa", "Calcula la pseudoinversa de A.", _RECTANGULAR
    ),
    "lu": Operation("Factorización LU", "Factoriza A con pivoteo.", "[[0, 2], [3, 4]]"),
    "cholesky": Operation(
        "Factorización de Cholesky",
        "Introduce A definida positiva.",
        "[[4, 2], [2, 3]]",
    ),
    "gauss": Operation(
        "Sistema · Gauss", "Para AX = B, introduce [A, B].", _SYSTEM, "binary"
    ),
    "inverse_system": Operation(
        "Sistema · inversa", "Para AX = B, introduce [A, B].", _SYSTEM, "binary"
    ),
    "cramer": Operation(
        "Sistema · Cramer", "Para AX = B, introduce [A, B].", _SYSTEM, "binary"
    ),
    "compatibility": Operation(
        "Sistema · compatibilidad",
        "Introduce [A, B] para clasificar el sistema por sus rangos.",
        "[[[1, 1], [2, 2]], [[3], [6]]]",
        "binary",
    ),
    "eigen": Operation(
        "Valores y vectores propios",
        "Introduce una matriz cuadrada A.",
        "[[2, 1], [1, 2]]",
    ),
    "diagonalize": Operation(
        "Diagonalización", "Introduce una matriz diagonalizable A.", "[[2, 1], [1, 2]]"
    ),
    "jordan": Operation(
        "Forma de Jordan", "Introduce una matriz cuadrada A.", "[[2, 1], [0, 2]]"
    ),
    "exponential": Operation(
        "Exponencial matricial",
        "Calcula eᴬ para una matriz cuadrada.",
        "[[0, 1], [0, 0]]",
    ),
    "svd": Operation(
        "Valores singulares · SVD",
        "Introduce una matriz A rectangular o cuadrada.",
        "[[3, 0, 0], [0, 2, 0]]",
    ),
    "expression": Operation(
        "Expresión libre con A y B",
        "Usa A y B desde las "
        "cuadrículas, o escribe matrices literales. Ejemplo: 2A + 3B.",
        "2A + 3B",
        "expression",
    ),
}


MODULES = {
    "definite_integrals": Module(
        "Integral definida",
        "Integral def.",
        "integral",
        {
            "definite": Operation(
                "Evaluar integral",
                "Introduce [f(x), límite inicial, límite final]. "
                "La función debe ser continua entre los límites.",
                "[x^2, 0, 2]",
            ),
        },
    ),
    "vector_calculus": Module(
        "Cálculo vectorial",
        "Vectorial",
        "multivariable",
        {
            "divergence": Operation(
                "Divergencia",
                "Introduce el campo [P, Q, R] con coordenadas x, y, z.",
                "[x^2, y^2, z^2]",
            ),
            "curl": Operation(
                "Rotacional",
                "Introduce el campo [P, Q, R] con coordenadas x, y, z.",
                "[-y, x, 0]",
            ),
        },
    ),
    "ode": Module(
        "Ecuaciones diferenciales",
        "Ec. diferenciales",
        "equation",
        {
            "linear": Operation(
                "EDO lineal de primer orden",
                "Para y′ + a(x)y = b(x), introduce [a(x), b(x)] "
                "con coeficientes continuos para todo x real.",
                "[2, x]",
            ),
        },
    ),
    "matrices": Module(
        "Álgebra de matrices",
        "Matrices",
        "table",
        MATRIX_OPERATIONS,
    ),
    "geometry": Module(
        "Geometría plana",
        "Geom. plana",
        "points",
        {
            "circle_area": Operation(
                "Área del círculo", "Introduce el radio en la forma [r].", "[3]"
            ),
            "triangle_area": Operation(
                "Área del triángulo", "Introduce los tres lados [a, b, c].", "[3, 4, 5]"
            ),
        },
    ),
    "analytic_geometry": Module(
        "Geometría analítica",
        "Geom. analítica",
        "graph",
        {
            "distance": Operation(
                "Distancia entre dos puntos",
                "Introduce los puntos del plano como [[x₁, y₁], [x₂, y₂]].",
                "[[0, 0], [3, 4]]",
            ),
            "midpoint": Operation(
                "Punto medio",
                "Introduce los puntos del plano como [[x₁, y₁], [x₂, y₂]].",
                "[[1, 2], [5, 8]]",
            ),
            "line": Operation(
                "Recta por dos puntos",
                "Introduce dos puntos distintos como [[x₁, y₁], [x₂, y₂]].",
                "[[2, 1], [2, 5]]",
            ),
        },
    ),
    "discrete": Module(
        "Matemáticas discretas",
        "Mat. discretas",
        "calculator",
        {
            "combinations": Operation(
                "Combinaciones sin repetición",
                "Introduce [n, k] para elegir k elementos entre n.",
                "[10, 3]",
            ),
            "permutations": Operation(
                "Variaciones sin repetición",
                "Introduce [n, k] para seleccionar y ordenar k elementos entre n.",
                "[10, 3]",
            ),
            "gcd": Operation(
                "Máximo común divisor",
                "Introduce dos enteros [a, b].",
                "[84, 30]",
            ),
        },
    ),
}
