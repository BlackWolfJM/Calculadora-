# Especificación del espacio de matrices

El módulo reproduce las tareas matemáticas públicas de MatrixCalc con una implementación propia en PySide6 y SymPy. La comparación usa los controles y la ayuda publicados el 6 de noviembre de 2026. Los casos de esta tabla verifican el comportamiento local.

| Referencia pública | Contrato en Calculadoras | Caso reproducible |
| --- | --- | --- |
| [Operaciones](https://matrixcalc.org/es/) | Cuadrículas A y B rectangulares, pegado y arrastre de texto, copia, limpieza, deshacer, rehacer, transferencia de operandos y reutilización de resultados. | Pegar los valores de `[[0,2],[3,4]]` en A. Calcular LU y transferir U a B. |
| [Operaciones](https://matrixcalc.org/es/) | Suma, resta, producto, transpuesta, traza, rango, adjunta, inversa y pseudoinversa. La suma y la resta exigen dimensiones iguales. El producto exige columnas de A iguales a filas de B. | Con A = `[[1,2],[3,4]]`, la transpuesta es `[[1,3],[2,4]]` y la traza es 5. |
| [Operaciones](https://matrixcalc.org/es/) | Multiplicación por escalar, forma escalonada y reducida, potencias, LU con pivoteo y Cholesky hermítica. Las potencias admiten exponentes enteros, fraccionarios y simbólicos cuando se pueden calcular, además de límites finitos verificables. | `[[[4,0],[0,9]],1/2]` produce `[[2,0],[0,3]]`. Para LU se verifica `PA=LU`. Para Cholesky se verifica `A=LL*`. |
| [Operaciones](https://matrixcalc.org/es/) | Expresión libre con A, B, literales con corchetes o llaves, funciones y ecuaciones matriciales simples. La identidad toma el orden del primer operando disponible. Las ecuaciones de una lista se resuelven de forma independiente. | Con los ejemplos A y B, `2A+3B` produce `[[17,22],[27,32]]`, `AX=B` produce `[[-3,-4],[4,5]]` y `Y+A=B` produce `[[4,4],[4,4]]`. |
| [Sistemas lineales](https://matrixcalc.org/es/slu.html) | Gauss, inversa, Cramer y compatibilidad por rangos. Gauss admite coeficientes rectangulares y varios términos independientes. Los casos compatibles indeterminados devuelven parámetros libres. | Con A = `[[1,2,3],[2,4,6]]`, B = `[[4],[8]]` da infinitas soluciones y B = `[[4],[9]]` es incompatible. |
| [Determinantes](https://matrixcalc.org/es/det.html) | Método automático, cofactores de una fila o columna elegida y reducción por filas. La traza registra intercambios y el producto de la diagonal. | En `[[0,2,1],[1,-1,2],[3,1,0]]` los cuatro métodos dan 16. |
| [Valores y vectores propios](https://matrixcalc.org/es/vectors.html) | Polinomio característico, valores y vectores propios con multiplicidad, diagonalización, Jordan, exponencial y SVD reducida. Se pueden reutilizar los factores matriciales por separado. | `[[2,1],[1,2]]` tiene valores propios 1 y 3. En la SVD rectangular se verifica `A=UΣV*`. |
| Ayuda de entrada de las cuatro páginas | Fracciones, decimales exactos y periódicos, notación científica, complejos, parámetros, funciones escalares y unidades angulares. La vista decimal admite de 2 a 15 cifras significativas y la copia conserva el valor exacto. | `{{0.1(6),sin(30deg),3!}}` devuelve `[[1/6,1/2,6]]`. |

## Integración

En **Matrices**, **Usar ejemplo** carga un caso completo. **Cuadrículas A/B** abre el editor. Los botones **A + B**, **A − B** y **A × B** calculan directamente con las dos cuadrículas. **Transponer** y **Determinante** calculan con la matriz activa. **Usar A/B** pasa los datos a la expresión para editarlos antes de resolver. La expresión libre toma A y B de las cuadrículas al resolver. Las celdas vacías dentro del tamaño elegido se interpretan como cero.

El proceso de cálculo recibe el texto, la operación y sus parámetros. El parser construye objetos simbólicos con operadores y funciones permitidos. El historial conserva los operandos y ajustes necesarios para repetir el cálculo. Se mantienen los identificadores `determinant`, `inverse` y `product`, así como las entradas anteriores con corchetes.

## Alcance y diferencias

- Se admiten matrices de hasta 8 × 8 y cálculos espectrales de hasta 5 × 5. Las potencias matriciales numéricas admiten exponentes reales entre −12 y 12, además de la opción de límite. Se conservan la cancelación y el límite de tiempo.
- Quedan pendientes las ecuaciones acopladas con varias matrices incógnitas y la compatibilidad exhaustiva con la sintaxis de MatrixCalc. La comparación del sitio se basó en sus páginas públicas.
- Los pasos detallan la eliminación por filas y la expansión por cofactores. Las factorizaciones espectrales muestran el método y los factores obtenidos, con comprobación cuando se puede establecer la identidad.
- Con parámetros simbólicos, algunas operaciones obtienen resultados genéricos sujetos a pivotes y denominadores distintos de cero. Las ramas degeneradas requieren un cálculo separado.

## Verificación

- `tests/unit/application/test_matrix_runtime.py` cubre ejemplos, determinantes, reconstrucción de factorizaciones, sistemas, sintaxis y validación.
- `tests/unit/presentation/test_main_window_dashboard.py` cubre el trabajador, el historial, las cuadrículas y la reutilización de factores.
