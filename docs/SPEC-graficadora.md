# Graficadora de Calculadoras

Fecha de análisis 5 de noviembre de 2026. La línea de base corresponde a los archivos del directorio de trabajo. El proyecto analizado carece de metadatos Git locales.

## Línea de base verificada en el código

| Área | Comportamiento observado | Evidencia |
| --- | --- | --- |
| Arranque | `run.py` inicializa el soporte de procesos de Windows. La entrada de escritorio crea una `QApplication`, registra el esquema local `math://` y abre la ventana principal. | [run.py](../run.py), [main.py](../src/main.py), [bootstrap.py](../src/bootstrap.py) |
| Operaciones | La ventana principal ofrece derivadas, integrales indefinidas y ecuaciones con pasos. El registro y el caso de uso separan la presentación de los módulos de cálculo. | [main_window.py](../src/presentation/main_window.py), [bootstrap.py](../src/bootstrap.py), [solve_expression.py](../src/application/solve_expression.py) |
| Entrada matemática | `MathParser` normaliza la entrada, genera un AST con Lark y lo valida. La gramática permite expresiones aritméticas, multiplicación implícita, funciones admitidas y una igualdad. Los símbolos son letras individuales. `SympyAdapter` convierte el AST para el cálculo. | [parser.py](../src/infrastructure/parsing/parser.py), [grammar.lark](../src/infrastructure/parsing/grammar.lark), [sympy_adapter.py](../src/infrastructure/sympy_adapter.py) |
| Gráfica educativa | El proceso de cálculo puede solicitar la gráfica de la expresión y su resultado en derivadas e integrales. El muestreo actual abarca 400 valores entre −10 y 10. La operación puede devolver el resultado matemático con un aviso si la gráfica falla. | [calculation_worker.py](../src/infrastructure/calculation_worker.py), [plotting.py](../src/infrastructure/plotting.py) |
| Render y recursos | `GraphView` carga Plotly desde recursos empaquetados mediante `math://` y recibe trazas JSON. La configuración de Qt WebEngine restringe acceso desde el contenido local. | [graph_view.py](../src/presentation/graph_view.py), [scheme_handler.py](../src/presentation/scheme_handler.py), [CalculadoraSuperInteligente.spec](../CalculadoraSuperInteligente.spec) |
| Datos locales | El historial de cálculos usa SQLite en la ruta de datos de usuario de Qt. El ejecutable y la prueba sin interfaz se construyen desde la misma entrada. | [bootstrap.py](../src/bootstrap.py), [sqlite_history.py](../src/infrastructure/sqlite_history.py), [run.py](../run.py), [test_packaging.py](../tests/integration/test_packaging.py) |

El proyecto requiere Python 3.13 o posterior y declara PySide6, SymPy, Lark y NumPy. Las comprobaciones habituales incluyen pytest, ruff y mypy. [pyproject.toml](../pyproject.toml)

## GeoGebra y Desmos como referencias

| Herramienta | Fortalezas para este proyecto | Limitaciones relevantes |
| --- | --- | --- |
| GeoGebra Calculator Suite | Reúne graficación, construcción geométrica dinámica, cálculo simbólico, 3D y probabilidad. Las construcciones hacen visibles las relaciones entre objetos. | La amplitud de herramientas y la división por modos aumentan las decisiones al empezar una exploración simple. Esta es una valoración de diseño a partir de la estructura de la suite. El uso del producto con sus materiales o archivos de idioma tiene condiciones específicas de redistribución. [Calculator Suite](https://help.geogebra.org/hc/en-us/articles/8379325433629-Calculator-Suite) · [Herramientas y funciones](https://help.geogebra.org/hc/en-us/articles/10445800380957-GeoGebra-Tools-and-Features-An-Overview) · [Licencia](https://www.geogebra.org/license) |
| Desmos Graphing Calculator | La lista de expresiones acerca la fórmula al resultado visual. Los deslizadores compartidos, las desigualdades, las restricciones, las tablas y las regresiones reducen los pasos de exploración. La marca también ofrece herramientas de geometría y graficación 3D. | Desmos indica que su calculadora no se considera un CAS. La conversión directa a tabla excluye curvas implícitas, paramétricas y polares. Su API para incrustación tiene condiciones propias. [Guía 2D](https://help.desmos.com/hc/en-us/articles/202529279-Desmos-Graphing-Calculator-User-Guide) · [Tablas](https://help.desmos.com/hc/en-us/articles/4405489674381-Tables) · [Deslizadores](https://help.desmos.com/hc/en-us/articles/202529069-Sliders-and-Movable-Points-in-a-Graph) · [Geometría](https://help.desmos.com/hc/en-us/articles/25041924352909-Desmos-Geometry-Tool-User-Guide) · [Guía 3D](https://help.desmos.com/hc/en-us/articles/25042283517069-Desmos-3D-User-Guide) · [Preguntas de evaluación](https://help.desmos.com/hc/en-us/articles/30913914831757-Assessment-Resources-FAQ) · [Términos de la API](https://www.desmos.com/api-terms) |

La decisión de producto es incorporar una graficadora propia, local y en español. El flujo principal toma la edición por expresiones y la retroalimentación visual de Desmos. La separación entre exploración algebraica, geometría, datos y 3D sigue la especialización útil de GeoGebra. El motor simbólico de Calculadoras aporta el flujo educativo con pasos en las operaciones disponibles.

## Contrato funcional propuesto

Esta sección fija los criterios de aceptación. La cobertura de cada punto se determina en la verificación de la implementación.

| Capacidad | Criterio de aceptación |
| --- | --- |
| Expresiones | Se pueden combinar, editar, ocultar y eliminar varias expresiones. Los errores indican la entrada afectada. Se distinguen curvas cartesianas, implícitas, paramétricas y polares mediante ejemplos que se pueden cargar y modificar. |
| Desigualdades | Se representa el lado que satisface la relación. Los ejemplos incluyen el disco `x^2+y^2<=9` y una región abierta. Si se muestran fronteras estrictas e inclusivas, su tratamiento visual permite distinguirlas. |
| Parámetros | Las expresiones que comparten una variable libre se actualizan al cambiar el mismo control. La notación y el valor se muestran en texto, además de la posición del deslizador. |
| Geometría | El plano mantiene una escala coherente entre ejes. Las construcciones derivadas de un punto conservan sus dependencias al cambiarlo. Los casos degenerados se comunican sin dar resultados numéricos inválidos. |
| 3D | Una superficie explícita de dos variables se explora desde distintas orientaciones. Los valores no reales o no finitos dejan huecos en la superficie. |
| Datos | Los pares válidos de una tabla se reflejan en la gráfica. Un ajuste informa el modelo y sus coeficientes, y describe entradas insuficientes o sin variación. |
| Navegación y salida | El espacio se abre desde la ventana principal. El usuario puede enfocar y operar los controles por teclado y volver a un encuadre inicial. Los formatos de salida disponibles se nombran explícitamente. Si se ofrece una sesión editable, la reapertura restaura la configuración representada por el archivo. |

## Cobertura de la implementación

La entrada **Graficadora** del menú principal abre un espacio de trabajo local. Los ejemplos se pueden cargar desde el selector y editar. [Ventana principal](../src/presentation/main_window.py) · [Espacio de trabajo](../src/presentation/graphing_workspace.py)

| Área | Implementación y alcance |
| --- | --- |
| 2D | Funciones explícitas, ecuaciones implícitas, inecuaciones, curvas polares y paramétricas, y restricciones conjuntivas entre llaves. Las relaciones se aproximan por muestreo en el intervalo visible. |
| Parámetros | Las letras libres disponibles se muestran como controles compartidos con deslizador y campo numérico. |
| Geometría | Puntos por coordenadas, segmentos, rectas, circunferencias, polígonos, punto medio, distancia e intersección de rectas. Las referencias a puntos con nombre permiten recomponer construcciones al editar las coordenadas o sus parámetros. |
| 3D | Superficies explícitas `z=f(x,y)`, curvas paramétricas y puntos. La vista de superficies ofrece una representación por contornos en entornos sin WebGL. |
| Datos | Tabla de pares, pegado de dos columnas tabuladas y ajustes polinómicos lineales, cuadráticos y cúbicos. El ajuste presenta su ecuación y R² cuando se puede calcular. |
| Cálculo | `derivative(f)` dibuja la derivada simbólica. `integral(f)` dibuja una primitiva para polinomios admitidos. El espacio principal conserva el flujo separado de resolución con pasos. |
| Archivos | La sesión JSON guarda expresiones, visibilidad, parámetros, tabla, modo y límites configurados. La exportación PNG genera una imagen de la gráfica. |

[Motor de muestreo](../src/infrastructure/graphing_workspace.py) · [Formato de sesión](../src/infrastructure/graph_session.py) · [Visor](../src/presentation/graph_view.py) · [Render local](../src/presentation/assets/plotly/workspace_plot.js)

## Arquitectura y reglas de interacción

- La presentación contiene el espacio de trabajo, sus controles y el encuadre. La evaluación recibe una instantánea de la entrada, los parámetros y el rango, y devuelve resultados o errores estructurados aptos para mostrar.
- Las expresiones de usuario pasan por un parser limitado antes de llegar a SymPy. Las relaciones y tuplas pueden separar sus operandos en la capa de graficación y validar cada uno mediante la gramática compartida.
- NumPy evalúa sobre intervalos y mallas acotados. El visor separa trazas cuando faltan valores y conserva la ventana de observación en cambios de parámetros. Una relación implícita muestreada constituye una aproximación visual.
- La fuente de cada objeto es la expresión o construcción editable. Las muestras y el resultado del ajuste se derivan de esa fuente. Los formatos de sesión deben guardar esa definición y validar los datos antes de sustituir la sesión activa.
- Los recursos se sirven localmente. Al cambiar de modo, se mantienen accesibles el plano, la lista o los controles apropiados para el modo. Las teclas de movimiento y los controles de zoom ofrecen una segunda vía de navegación.
- La interfaz comparte el fondo de papel, el texto oscuro, el verde mineral y los focos visibles del sistema existente. Las marcas se diferencian también por nombre, forma o estilo de línea cuando el color por sí solo no basta. [Diseño de Calculadoras](../DESIGN.md)

## Comprobaciones

1. Abrir la graficadora desde la aplicación y volver a una derivada con su vista previa original.
2. Graficar una constante, una función con polo, un círculo implícito y un dominio real parcial. Confirmar que los segmentos no atraviesan valores indefinidos.
3. Cambiar un parámetro compartido y comprobar que se actualizan las trazas correspondientes. Editar una fórmula incorrecta junto a otra válida.
4. Revisar construcciones en escala 1:1, una superficie 3D, una tabla con filas vacías y un ajuste con suficientes datos.
5. Comprobar las salidas y la restauración de sesión cuando se ofrezcan. Probar el tamaño inicial de 1180 × 760 y el mínimo de la ventana principal de 820 × 600.
6. Ejecutar la suite habitual y, cuando se modifiquen recursos o dependencias de distribución, construir y probar el ejecutable de Windows.

La paridad con catálogos completos, servicios de aula, formatos propietarios y bibliotecas de actividades de los productos de referencia requiere alcance y validación propios.
