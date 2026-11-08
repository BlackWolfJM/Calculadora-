# Encargo para Antigravity CLI

Mejora Calculadoras, la aplicación de escritorio en español basada en PySide6 y SymPy. Trabaja por fases y entrega cambios funcionales, pruebas y una lista de brechas. Usa las personalizaciones disponibles en `.agent/` y `.agents/` que correspondan a cada tarea. Al terminar cada fase, registra los archivos cambiados, las comprobaciones ejecutadas y los resultados que pudiste observar.

## 1. Espacio de Matrices

Empieza por esta fase. Toma como base `docs/SPEC-matrixcalc.md`, el módulo Matrices actual y el comportamiento público de [MatrixCalc](https://matrixcalc.org/es/). Crea un espacio con A y B visibles en ventanas anchas y pestañas en ventanas estrechas. Ofrece accesos directos para suma, resta, producto, transpuesta y determinante. Agrupa sistemas, factorizaciones y análisis espectral. El usuario debe poder resolver desde las cuadrículas y enviar cada factor o resultado a A o B.

Conserva las 26 operaciones, el formato exacto, la precisión decimal, la entrada textual, los identificadores de operación, la cancelación y el historial. Integra la interfaz en PySide6 y reutiliza el proceso de cálculo. Comprueba los tamaños de 820 × 600 y 1180 × 760, teclado, pegado de matrices, recuperación desde el historial y una LU con transferencia de U. En esta fase limita los cambios a la interfaz de matrices, su conexión en la ventana principal, el catálogo, el tema y sus pruebas.

## 2. Resolver y Explorar

Integra el solucionador y la graficadora en un flujo de ida y vuelta. Usa `docs/SPEC-graficadora.md` como contrato de base. Al abrir una gráfica desde una resolución, conserva la expresión, los parámetros, el resultado y el procedimiento para poder volver. Prueba una derivada y una integral definida con su intervalo sombreado. Ofrece controles de parámetros junto a las expresiones que los usan, siguiendo el patrón de [Desmos](https://www.desmos.com/calculator?lang=es). Evalúa las interacciones geométricas directas con [GeoGebra](https://www.geogebra.org/calculator) como referencia.

## 3. Cuaderno local

Amplía el historial SQLite con una vista de sesiones y ejercicios, búsqueda, filtros por tema, favoritos y notas. El usuario debe poder volver a abrir un cálculo o una sesión gráfica y continuar editándolos. Define una migración compatible con los datos existentes y prueba la reapertura. Usa el flujo de estudio de [Symbolab](https://es.symbolab.com/solver/derivative-calculator) como referencia. Empieza por sesiones y ejercicios recientes antes de añadir métricas de práctica.

## 4. Cobertura matemática

Añade límites y entrada de ecuaciones diferenciales con condiciones iniciales. Después amplía integrales impropias y múltiples, y explora lógica, relaciones y grafos para matemáticas discretas. Para cada operación define el dominio admitido, ejemplos editables, qué pasos se muestran, cómo se verifica el resultado y qué errores quedan cubiertos. Usa [MathDF](https://mathdf.com/dif/es/) y los [ejemplos de Wolfram|Alpha](https://www.wolframalpha.com/examples/pro-features/step-by-step-solutions/step-by-step-calculus/) como referencias públicas.

## Agentes, skills y comprobaciones

| Trabajo | Personalizaciones del proyecto |
| --- | --- |
| Inventario funcional y contratos | `spec-miner`, `matrixcalc-parity`, `code-to-spec`, `ecc-context-research` |
| Arquitectura y reparto | `architect`, `planner`, `ecc-plan`, `ecc-orchestrate` |
| Interacción, accesibilidad y diseño | `design-qa`, `accessibility-and-inclusive-visualization`, `data-visualization`, `web-design-guidelines` como referencia de interacción y foco |
| Pruebas y revisión | `tdd-guide`, `e2e-runner`, `code-reviewer`, `tdd-workflow`, `ecc-code-review`, `ecc-e2e`, `ecc-verify` |
| Fallos de build o regresiones | `build-error-resolver`, `refactor-cleaner`, `ecc-build-fix` cuando corresponda |
| Parser, archivos de sesión y migraciones | `security-reviewer`, `security-review` |
| Documentación de lo implementado | `doc-updater`, `ecc-update-docs`, `ecc-update-codemaps` |

Descubre los recursos con las herramientas de la sesión. Usa el grafo del código si está disponible, el navegador para referencias públicas, Qt para probar la interfaz y la terminal para pytest con `.venv/Scripts/python.exe`. Mantén los MCP desactivados en su estado actual. Los subagentes de implementación deben tener ámbitos de edición separados. Comprueba cada fase antes de avanzar a la siguiente y distingue las capacidades verificadas de las propuestas. Trabaja dentro del proyecto con la política de permisos de Antigravity. La entrega es local y se basa en implementación propia.
