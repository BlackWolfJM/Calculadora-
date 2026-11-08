# Especificación Técnica Integral — Calculadoras (Reverse-Engineered Spec & Estudio Gráfico GeoGebra + Desmos)

> Generado mediante la skill `code-to-spec`, agentes de arquitectura de **Everything Claude Code (ECC)** y skills de diseño de visualización (`data-visualization`, `visualization-strategy-and-critique`, `d3-data-visualization`, `threejs-data-visualization`, `dashboards-and-real-time-visualization`, `accessibility-and-inclusive-visualization`, `testing-data-visualizations`, `frontend-app-builder`, `web-design-guidelines`).

---

## 1. Arquitectura General y Stack Tecnológico

### 1.1 Stack Tecnológico Exacto
- **Lenguaje y Runtime**: Python `>=3.13` (ejecutándose sobre Python `3.14.6`).
- **Framework GUI de Escritorio**: `PySide6 >= 6.11.0` (`QtWidgets`, `QtGui`, `QtCore`, `QtWebEngineWidgets`, `QtWebEngineCore`).
- **Motor Simbólico y Numérico**:
  - `SymPy >= 1.14.0` para álgebra computacional (CAS), derivación, integración, resolución de ecuaciones, cálculo multivariable, límites, series de Taylor y detección de singularidades.
  - `Lark >= 1.3.1` para el parser gramatical determinista (`MathParser`) con localización exacta de errores (`StructuredMathError`).
  - `NumPy >= 2.4.4` para evaluación vectorizada (`sp.lambdify(..., "numpy")`) en mallas 2D y 3D.
- **Renderizado Matemático y Gráfico Offline**:
  - **KaTeX local** (`src/presentation/assets/katex/katex.min.js`) servido mediante esquema seguro `math://katex/`.
  - **Plotly.js local** (`src/presentation/assets/plotly/plotly.min.js`) servido mediante esquema seguro `math://plotly/`.
- **Persistencia Local**: `sqlite3` nativo (`SQLiteHistoryRepository`) en `history.db` con consultas parametrizadas.
- **Calidad y Verificación**: `pytest`, `pytest-qt`, `pytest-cov`, `ruff`, `mypy`, `pyinstaller`.

### 1.2 Arquitectura Hexagonal / Clean Architecture
```
src/
├── domain/                  # Núcleo puro (sin dependencias de UI ni SQLite)
│   ├── expressions/         # AST matemático (ExpressionNode, NumberNode, SymbolNode, etc.)
│   ├── modules/             # Módulos matemáticos registrados en ModuleRegistry
│   │   ├── derivatives/     # Derivadas simbólicas, orden 1..5, pasos educativos
│   │   ├── integrals/       # Integrales indefinidas y definidas [a, b], pasos
│   │   ├── equations/       # Ecuaciones algebraicas y sistemas lineales
│   │   └── multivariable/   # Valor en punto, parciales, gradiente, direccional, laplaciano
│   ├── errors.py            # StructuredMathError (code, message, line, column, suggestion)
│   ├── history.py           # HistoryEntry y protocolo HistoryRepository
│   ├── registry.py          # ModuleRegistry
│   ├── responses.py         # SolutionResponse, CalculationBlock, ResultItem, MathPayload
│   ├── steps.py             # EducationalStep, StepOutcome, StepCoverage, StepStatus
│   └── verification.py      # MathVerifier (verificación simbólica y numérica)
├── application/             # Casos de uso y orquestación de dominio
│   ├── build_math_runtime.py# Factoría aislada del motor matemático para procesos hijos
│   ├── solve_expression.py  # SolveExpressionUseCase
│   └── graphing_studio.py   # Motor del Estudio Gráfico Definitivo (GeoGebra + Desmos)
├── infrastructure/          # Adaptadores concretos (Lark, SymPy, SQLite, Multiprocessing)
│   ├── parsing/             # MathParser (gramática Lark -> AST de dominio)
│   ├── persistence/         # SQLiteHistoryRepository
│   ├── calculation_worker.py# Proceso hijo spawn y serialización IPC schema_version=1
│   ├── plotting.py          # Generación de trazas acotadas con manejo de singularidades
│   └── sympy_adapter.py     # Puente seguro entre AST de dominio y objetos SymPy
└── presentation/            # Interfaz gráfica PySide6 ("Hoja de Estudio Académica")
    ├── assets/              # KaTeX y Plotly empaquetados para ejecución 100% offline
    ├── calculation_process_controller.py # Controlador IPC con timeout, cancelación y retiro
    ├── graphing_studio_widget.py         # Estudio Gráfico Interactivo (GeoGebra + Desmos)
    ├── graph_view.py        # Visor QWebEngineView + Plotly 2D/3D/Contorno con resumen accesible
    ├── history_dialog.py    # Diálogo de historial con búsqueda, filtro por módulo y copia
    ├── main_window.py       # Ventana principal, barra lateral, editor, teclado y pestañas
    ├── math_view.py         # Visor QWebEngineView + KaTeX con auto-ajuste y sanitización
    ├── scheme_handler.py    # MathSchemeHandler (math://katex, math://plotly, math://base)
    └── theme.py             # Sistema de diseño, paleta, tipografía, iconos vectoriales y QSS
```

---

## 2. Fronteras de Seguridad y Aislamiento Offline

1. **Esquema `math://` Endurecido ([`MathSchemeHandler`](file:///e:/calculadoras/src/presentation/scheme_handler.py))**:
   - Solo permite hosts en `ALLOWED_HOSTS = {"katex", "plotly", "base"}`.
   - Solo permite extensiones en `ALLOWED_EXTENSIONS = {".js", ".css", ".woff", ".woff2", ".ttf", ".html", ".htm", ".svg", ".png", ".map"}`.
   - Decodifica `unquote()`, resuelve con `Path.resolve()` y verifica `full_path.is_relative_to(self._assets_dir)` para bloquear cualquier intento de *path traversal* (`..`, `%2e%2e`, rutas absolutas).
2. **Aislamiento de `QWebEngineView` ([`MathView`](file:///e:/calculadoras/src/presentation/math_view.py) y [`GraphView`](file:///e:/calculadoras/src/presentation/graph_view.py))**:
   - `LocalContentCanAccessRemoteUrls = False` (cero acceso a internet o CDNs).
   - `LocalContentCanAccessFileUrls = False` (cero acceso a `file://`).
   - `JavascriptCanOpenWindows = False`.
3. **Mitigación de XSS y Bombas de Macros en KaTeX**:
   - `trust: false`, `maxSize: 20`, `maxExpand: 1000`, `throwOnError: false`.
   - El texto libre (reglas, explicaciones y advertencias) jamás se concatena con `innerHTML`; se inserta mediante nodos DOM seguros (`document.createTextNode` / `span.textContent`), procesando únicamente segmentos matemáticos delimitados con KaTeX.
4. **Aislamiento de Procesos para Cálculo Simbólico ([`CalculationProcessController`](file:///e:/calculadoras/src/presentation/calculation_process_controller.py))**:
   - Los cálculos simbólicos pesados corren en un proceso separado (`multiprocessing.get_context("spawn")`) con límite de tiempo (`timeout_ms = 15000`), cancelación inmediata y drenaje acotado de tuberías (`_MAX_DRAIN_ITERATIONS = 16`).

---

## 3. Esquema de Persistencia (`SQLiteHistoryRepository`)

Tabla SQLite `history`:
| Columna | Tipo SQLite | Descripción |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Identificador único autoincremental |
| `expression` | `TEXT NOT NULL` | Expresión original introducida por el usuario |
| `module_id` | `TEXT NOT NULL` | ID del módulo (`derivatives`, `integrals`, `equations`, `multivariable`) |
| `result_latex` | `TEXT NOT NULL` | Resultado principal en formato LaTeX |
| `timestamp` | `TEXT NOT NULL` | Fecha/hora ISO-8601 (`YYYY-MM-DD HH:MM:SS`) |

Operaciones del protocolo [`HistoryRepository`](file:///e:/calculadoras/src/domain/history.py):
- `add(entry: HistoryEntry) -> None`
- `get_all() -> list[HistoryEntry]` (orden descendente por `id`)
- `clear() -> None`

---

## 4. Evaluación Comparativa: GeoGebra vs. Desmos y Diseño de la Graficadora Definitiva

### 4.1 Análisis de Fortalezas y Debilidades

| Dimensión | **Desmos Graphing Calculator** | **GeoGebra Classic / CAS Suite** | **Nuestra Síntesis: Estudio Gráfico Definitivo (`Calculadoras`)** |
|---|---|---|---|
| **Lista de Expresiones y Ergonomía** | **Fortaleza sobresaliente**: Lista lateral limpia de funciones $f_1(x), f_2(x), \dots$ con colores semánticos, activación/ocultación instantánea y baja fricción cognitiva. | **Debilidad**: Vista algebraica recargada de objetos internos y barra de herramientas modal con decenas de menús ocultos. | **Adopta el modelo Desmos**: Lista de expresiones clara con selector de color, visibilidad por serie, estado en vivo y galería de ejemplos curados. |
| **Deslizadores de Parámetros (Sliders)** | **Fortaleza sobresaliente**: Detección automática de parámetros libres ($a, b, c$ en $a\sin(bx+c)$) con controles de rango y actualización inmediata. | **Debilidad**: Creación manual de deslizadores mediante diálogos modales. | **Adopta y mejora Desmos**: Detección automática de parámetros simbólicos libres ($a, b, c, k, m, n, \dots$) con sliders interactivos y control numérico exacto. |
| **Puntos Notables (Points of Interest)** | **Fortaleza sobresaliente**: Identificación inmediata de raíces ($f(x)=0$), intersección con eje $Y$ ($f(0)$), extremos locales ($f'(x)=0$) e intersecciones entre curvas ($f(x)=g(x)$). | **Fortaleza media**: Requiere invocar comandos explícitos (`Raíz(f)`, `Extremo(f)`, `Interseca(f,g)`). | **Fusión Desmos + SymPy CAS**: Detección automática de raíces, extremos locales, ordenada al origen e intersecciones con coordenadas exactas/numéricas y marcadores visuales en la gráfica. |
| **Herramientas Geométricas y de Cálculo (CAS)** | **Debilidad**: Carece de herramientas explícitas de construcción de cálculo (recta tangente/normal con ecuación simbólica, polinomios de Taylor, sumas de Riemann explícitas con error). | **Fortaleza sobresaliente**: Construcción directa de recta tangente y normal en $x_0$, área de integral definida $\int_a^b f(x)\,dx$ con particiones de Riemann/trapecios, derivada $f'(x)$ y serie de Taylor $T_n(x, x_0)$. | **Adopta y potencia GeoGebra**: Panel de *Laboratorio de Cálculo* integrado: recta tangente y normal en $x_0$, área sombreada $\int_a^b f(x)\,dx$ + rectángulos de Riemann (izquierda, derecha, punto medio, trapecio), superposición de $f'(x)$ y polinomio de Taylor $T_n(x, x_0)$ con fórmulas simbólicas exactas en KaTeX. |
| **Tabla de Valores** | **Fortaleza sobresaliente**: Conversión en un clic de cualquier lista de funciones en una tabla comparativa $(x, f_1(x), f_2(x))$. | **Debilidad**: Hoja de cálculo separada y desconectada del flujo principal. | **Adopta Desmos**: Generador integrado de Tabla de Valores para todas las funciones activas con rango $[x_{\text{inicio}}, x_{\text{fin}}]$ y paso $\Delta x$ configurable y copiable. |
| **Cálculo Multivariable 2D/3D ($z = f(x,y)$)** | **Debilidad**: Separado en otra herramienta y sin inspección simbólica integrada de gradiente/laplaciano. | **Fortaleza sobresaliente**: Vista gráfica 3D integrada con superficies $z=f(x,y)$, curvas de nivel y plano tangente / vector gradiente. | **Adopta GeoGebra + `MultivariableModule`**: Modo **Superficie 3D y Mapa de Contorno 2D** para funciones $z = f(x,y)$ con evaluación en $(x_0, y_0)$, plano tangente $z = f(x_0,y_0) + f_x(x-x_0) + f_y(y-y_0)$, vector gradiente $\nabla f$ y laplaciano $\nabla^2 f$. |
| **Privacidad, Offline y Accesibilidad** | **Debilidad**: Dependiente de nube/web propietaria en muchos flujos. | **Debilidad**: Pesado y con problemas de contraste/foco en escritorio. | **100% Offline, Seguro y Accesible**: Ejecución local con `SymPy` + `NumPy` + `Plotly` + `KaTeX` vía `math://`, paleta de alto contraste (Okabe-Ito adaptada) y resumen textual accesible para lectores de pantalla. |

---

## 5. Especificación del Motor del Estudio Gráfico (`src/application/graphing_studio.py`)

### 5.1 Modelos de Datos Inmutables
- `FunctionExpressionSpec`:
  - `expr_id: str`
  - `expression: str`
  - `label: str`
  - `color: str`
  - `visible: bool = True`
  - `line_dash: str = "solid"`
- `CalculusOverlayConfig`:
  - `show_points_of_interest: bool = True` (raíces, corte eje Y, extremos locales, intersecciones)
  - `show_derivative: bool = False` (superpone $f_1'(x)$)
  - `tangent_enabled: bool = False` y `tangent_x0: float = 1.0` (recta tangente y recta normal en $x_0$)
  - `integral_enabled: bool = False`, `integral_a: float = 0.0`, `integral_b: float = 2.0`, `riemann_Rule: str = "midpoint"`, `riemann_n: int = 12`
  - `taylor_enabled: bool = False`, `taylor_order: int = 3`, `taylor_x0: float = 0.0`
- `PointOfInterest`:
  - `kind: str` (`"root"`, `"y_intercept"`, `"local_min"`, `"local_max"`, `"intersection"`)
  - `label: str`
  - `x: float`
  - `y: float`
  - `series_name: str`
- `StudioAnalysisSummary`:
  - `primary_latex: str`
  - `derivative_latex: str`
  - `tangent_latex: str`
  - `normal_latex: str`
  - `taylor_latex: str`
  - `integral_exact_latex: str`
  - `integral_numeric: float | None`
  - `riemann_numeric: float | None`
  - `points_of_interest: list[PointOfInterest]`
  - `table_headers: list[str]`
  - `table_rows: list[list[str]]`
  - `multivariable_summary: dict[str, str]` (para modo 3D/Contorno: $f(x_0,y_0)$, $\nabla f$, plano tangente, $\nabla^2 f$)

### 5.2 Capacidades Algorítmicas
1. **Detección de Parámetros Libres (`detect_free_parameters`)**:
   - Analiza todas las expresiones activas con `MathParser` + `SympyAdapter`.
   - Extrae todos los símbolos libres distintos de las variables independientes (`x`, o `x, y` en modo 3D/contorno) y constantes reservadas (`pi`, `e`), devolviendo una lista ordenada de nombres de parámetros para generar deslizadores interactivos automáticamente.
2. **Evaluación Vectorizada Segura con Corte en Singularidades**:
   - Evalúa sobre malla `np.linspace(x_min, x_max, num_samples)` con `np.errstate(all="ignore")`.
   - Detecta discontinuidades/singularidades simbólicas (`sp.singularities`) y saltos abruptos ($\Delta y$ divergente) insertando `None` con `connectgaps: False` para evitar líneas verticales falsas en asíntotas como $\tan(x)$ o $1/x$.
3. **Detección Híbrida de Puntos Notables (Desmos-style)**:
   - Combina resolución simbólica acotada y búsqueda numérica por cambio de signo + bisección/interpolación sobre la malla para encontrar:
     - **Raíces**: $f(x) = 0$ en $[x_{\min}, x_{\max}]$.
     - **Ordenada al origen**: $(0, f(0))$ si $0 \in [x_{\min}, x_{\max}]$.
     - **Extremos locales**: $f'(x) = 0$ verificando cambio de signo en $f'(x)$ (clasificando mínimo local vs máximo local).
     - **Intersecciones**: $f_1(x) - f_2(x) = 0$ entre las dos primeras curvas visibles.
4. **Herramientas Geométricas y de Cálculo (GeoGebra-style)**:
   - **Recta Tangente y Normal en $x_0$**: Calcula $y_t(x) = f(x_0) + f'(x_0)(x - x_0)$ y $y_n(x) = f(x_0) - \frac{1}{f'(x_0)}(x - x_0)$, genera sus trazas y el punto de tangencia $(x_0, f(x_0))$, además de su ecuación exacta en LaTeX.
   - **Área de Integral Definida y Sumas de Riemann**: Sombrea la región bajo $f_1(x)$ en $[a, b]$ (`fill: "tozeroy"`), dibuja los $n$ rectángulos o trapecios de aproximación, y compara el valor exacto/numérico de $\int_a^b f(x)\,dx$ frente a la suma de Riemann $S_n$.
   - **Polinomio de Taylor $T_n(x; x_0)$**: Calcula `sp.series(expr, x, x0, n + 1).removeO()`, genera su traza superpuesta y expone la fórmula desarrollada en KaTeX.
5. **Explorador Multivariable 3D y Contorno 2D ($z = f(x, y)$)**:
   - Genera mallas bidimensionales $(X, Y) \in [x_{\min}, x_{\max}] \times [y_{\min}, y_{\max}]$ para trazas `surface` (3D interactivo con plano tangente en $(x_0, y_0)$) o `contour` (mapa de curvas de nivel 2D con vector gradiente $\nabla f(x_0, y_0)$).
   - Se integra con [`MultivariableModule`](file:///e:/calculadoras/src/domain/modules/multivariable/module.py) para mostrar el valor exacto $f(x_0, y_0)$, las derivadas parciales $\frac{\partial f}{\partial x}, \frac{\partial f}{\partial y}$, el gradiente $\nabla f$ y el laplaciano $\nabla^2 f$.

---

## 6. Especificación de Componentes UI y Jerarquía Visual

### 6.1 Sistema de Diseño ([`theme.py`](file:///e:/calculadoras/src/presentation/theme.py))
- **Dirección Estética**: *Hoja de Estudio Académica* (cálida, serena, de alto contraste y libre de fatiga visual).
- **Paleta Semántica**:
  - `BACKGROUND = "#F5F3EE"` (papel marfil cálido), `SURFACE = "#FFFFFF"`, `SURFACE_ALT = "#ECE8DF"`, `SIDEBAR_BG = "#EDEAE2"`.
  - `TEXT = "#24332F"` (tinta pizarra profunda, contraste $>11:1$), `TEXT_MUTED = "#5A6B65"`.
  - `PRIMARY = "#216653"` (verde esmeralda académico), `PRIMARY_SOFT = "#E3EFEA"`, `ACCENT_GOLD = "#9A6700"`.
  - Paleta de series gráficas apta para daltonismo (inspirada en Okabe-Ito): `#216653` (Esmeralda), `#D55E00` (Bermellón), `#0072B2` (Azul Cobalto), `#CC79A7` (Púrpura), `#E69F00` (Ámbar), `#009E73` (Turquesa).
- **Tipografía**:
  - Interfaz: `"Segoe UI", "Inter", sans-serif`.
  - Editor de código matemático y tablas numéricas: `"Cascadia Mono", "Consolas", monospace` con `font-variant-numeric: tabular-nums`.
  - Fórmulas simbólicas: `KaTeX_Main` local a través de `MathView`.

### 6.2 Ventana Principal ([`MainWindow`](file:///e:/calculadoras/src/presentation/main_window.py))
- **Barra Lateral de Navegación**:
  - Módulos de resolución simbólica: **Derivadas** (`derivatives`), **Integrales** (`integrals`), **Ecuaciones** (`equations`), **Multivariable** (`multivariable`).
  - Modo de exploración visual completa: **Graficadora** (`graphing`, atajo `Ctrl+G`), que conmuta el área de trabajo al **Estudio Gráfico GeoGebra + Desmos** o permite enviar cualquier expresión resuelta directamente al estudio gráfico.
  - Acceso secundario a **Historial** (`Ctrl+H`) y guía de atajos de teclado.
- **Adaptabilidad Responsiva (`1180×760` y `820×600`)**:
  - En anchos compactos (`width < 1000`), la barra lateral se compacta a `176px`, las tarjetas de lectura de resultado apilan verticalmente el encabezado y la verificación (`QBoxLayout.Direction.TopToBottom`), y los controles mantienen alturas táctiles/accesibles sin recortar fórmulas.

### 6.3 Estudio Gráfico Interactivo ([`GraphingStudioWidget`](file:///e:/calculadoras/src/presentation/graphing_studio_widget.py))
- **Columna Izquierda (Estilo Desmos + Controles GeoGebra)**:
  1. **Selector de Modo**: `2D Funciones y = f(x)`, `2D Mapa de Contorno z = f(x,y)`, `3D Superficie z = f(x,y)`.
  2. **Lista de Expresiones Multi-Función**: Hasta 4 funciones simultáneas con casilla de visibilidad, insignia de color, editor monoespaciado y galería de ejemplos rápidos (*Oscilación amortiguada*, *Polinomio cúbico + tangente*, *Intersección trigonométrica*, *Silla de montar 3D*, *Ondas gaussianas 3D*).
  3. **Deslizadores Automáticos de Parámetros**: Generados dinámicamente al escribir parámetros libres como `a*sin(b*x) + c`, con slider continuo y `QDoubleSpinBox` sincronizado.
  4. **Laboratorio de Cálculo (Estilo GeoGebra)**:
     - Casillas para **Puntos notables** (raíces, extremos, intersecciones), **Derivada $f_1'(x)$**, **Recta tangente y normal en $x_0$**, **Integral definida $\int_a^b f_1(x)\,dx$ + Sumas de Riemann ($n$ particiones)** y **Polinomio de Taylor $T_n(x, x_0)$**.
     - Controles de dominio $[x_{\min}, x_{\max}]$ y punto $(x_0, y_0)$.
- **Columna Derecha (Lienzo Visual + Inspector Simbólico y Tabla)**:
  1. **Lienzo `GraphView` Interactivo**: Gráfica Plotly con trazas enriquecidas, sombreado de áreas, rectángulos de Riemann, marcadores de puntos notables con etiquetas directas y resumen accesible inferior.
  2. **Pestañas de Inspección Inferior**:
     - **Análisis Simbólico (CAS)**: Muestra en `MathView` (KaTeX) las fórmulas exactas de $f(x)$, $f'(x)$, la recta tangente/normal en $x_0$, el polinomio de Taylor, el valor exacto/numérico de la integral y la suma de Riemann (o el gradiente $\nabla f$, plano tangente y laplaciano $\nabla^2 f$ en modo 3D/Contorno).
     - **Puntos Notables**: Lista estructurada y seleccionable de raíces, extremos locales, ordenada al origen e intersecciones detectadas.
     - **Tabla de Valores**: Tabla numérica $(x, f_1(x), f_2(x), \dots)$ con configuración de $x_{\text{inicio}}, x_{\text{fin}}, \Delta x$ y botón para copiar como CSV/TSV al portapapeles.

### 6.4 Diálogo de Historial ([`HistoryDialog`](file:///e:/calculadoras/src/presentation/history_dialog.py))
- Búsqueda instantánea por texto (expresión o resultado) y filtro por módulo (`Todos`, `Derivadas`, `Integrales`, `Ecuaciones`, `Multivariable`).
- Eliminación del borde negro interior de selección nativa de Qt (`outline: none` en `QListWidget`), reemplazado por un estado seleccionado limpio con borde esmeralda de `2px`.
- Acciones explícitas: **Volver a resolver** (`Enter` o doble clic), **Copiar resultado**, **Borrar historial** y **Cerrar** (`Esc`).

