"""
Estudio Gráfico Definitivo (Síntesis GeoGebra + Desmos) para Calculadoras.

Integra:
- Lista multi-expresión con colores semánticos y visibilidad por fila (estilo Desmos).
- Deslizadores automáticos de parámetros libres con animación Play/Pause en tiempo real.
- Detección automática e inspección de puntos notables: raíces, intersección con eje Y,
  extremos locales e intersecciones entre curvas.
- Herramientas constructivas y de cálculo simbólico (estilo GeoGebra): recta tangente y
  normal en x₀, integral definida sombreada ∫[a,b], sumas de Riemann, Taylor,
  construcciones geométricas (punto, segmento, recta, circunferencia, polígono),
  curvas polares, paramétricas, implícitas, inecuaciones, mapa de contorno, gradiente 2D
  y superficies 3D con plano tangente.
- Generador de Tabla de Valores (x, f₁(x), f₂(x), ...) y tabla de datos (x, y)
  con regresión polinómica.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.infrastructure.graph_session import (
    GraphSession,
    load_graph_session,
    save_graph_session,
)
from src.infrastructure.graphing_workspace import (
    MAX_COORDINATE,
    PALETTE,
    GraphResult,
    build_graph,
    evaluate_function_table,
)
from src.presentation import theme
from src.presentation.graph_view import GraphView

_X_RANGE = (-10.0, 10.0)
_Y_RANGE = (-10.0, 10.0)
_T_RANGE = (0.0, 6.283185307179586)
_ROW_LIMIT = 24
_DATA_LIMIT = 200
_FIT_DEGREES = {"linear": 1, "quadratic": 2, "cubic": 3}
_QSS = f"""
QWidget#graphing-workspace, QFrame#graph-toolbar {{ background: {theme.BACKGROUND}; }}
QFrame#graph-plot, QFrame#graph-controls {{ background: {theme.SURFACE};
    border: 1px solid {theme.BORDER}; border-radius: 10px; }}
QFrame#notable-card {{ background: {theme.RESULT_SURFACE};
    border: 1px solid {theme.BORDER}; border-radius: 8px; }}
QLabel#graph-title {{ font-size: 24px; font-weight: 700; color: {theme.TEXT}; }}
QLabel#graph-subtitle {{ color: {theme.MUTED}; font-size: 13px; }}
QLabel#graph-section {{ font-size: 15px; font-weight: 600; color: {theme.TEXT}; }}
QLabel#graph-note {{ color: {theme.MUTED}; font-size: 12px; }}
QLabel#graph-status {{ color: {theme.MUTED}; font-size: 13px; }}
QLabel#graph-expression-feedback {{ color: {theme.PRIMARY}; font-size: 12px;
    font-family: Consolas; }}
QLabel#graph-expression-feedback[invalid="true"] {{ color: {theme.DANGER};
    font-family: "Segoe UI"; }}
QLineEdit#graph-expression {{ border: 1px solid #87958D; border-radius: 6px;
    padding: 6px 8px; font-family: Consolas; font-size: 14px; min-height: 32px; }}
QLineEdit#graph-expression:focus, QDoubleSpinBox:focus,
QTableWidget:focus {{ border: 2px solid {theme.FOCUS}; }}
QPushButton {{ min-height: 34px; padding: 0 10px;
    font-size: 13px; border-radius: 6px; }}
QPushButton[graphRole="primary"] {{ background: {theme.PRIMARY}; color: white;
    border-color: {theme.PRIMARY}; font-weight: 600; }}
QPushButton[graphRole="primary"]:hover {{ background: #174B3D; }}
QPushButton[graphRole="primary"]:disabled {{ background: {theme.SURFACE_ALT};
    color: {theme.MUTED}; border-color: {theme.BORDER}; }}
QPushButton[graphRole="primary"]:focus {{ border: 2px solid #D1F0E4; }}
QPushButton[graphRole="mode"]:checked {{ background: #DDECE2;
    color: {theme.PRIMARY}; border-color: {theme.PRIMARY}; font-weight: 700; }}
QComboBox, QDoubleSpinBox {{ min-height: 34px; padding: 0 8px;
    font-size: 13px; border: 1px solid #87958D; border-radius: 6px; }}
QTabBar::tab {{ padding: 8px 11px; font-size: 13px; font-weight: 600; }}
QTableWidget {{ gridline-color: {theme.BORDER}; border: 1px solid {theme.BORDER};
    selection-background-color: #DDECE2; selection-color: {theme.TEXT};
    font-family: Consolas; font-size: 13px; }}
QHeaderView::section {{ background: {theme.SURFACE_ALT}; border: none;
    border-bottom: 1px solid {theme.BORDER}; padding: 6px; font-weight: 600; }}
QSplitter::handle {{ background: {theme.BACKGROUND}; }}
"""


@dataclass(frozen=True)
class _Example:
    name: str
    mode: str
    expressions: tuple[str, ...] = ()
    parameters: tuple[tuple[str, float], ...] = ()
    data: tuple[tuple[float, float], ...] = ()
    regression: str = "none"


_EXAMPLES = (
    _Example(
        "Ondas y parámetros (Desmos)",
        "2d",
        ("y=a*sin(x)", "y=cos(x)"),
        (("a", 1.5),),
    ),
    _Example(
        "Cálculo: Tangente y extremos (GeoGebra)",
        "2d",
        (
            "y=x^3-3*x",
            "tangent(x^3-3*x, a)",
            "extrema(x^3-3*x)",
            "roots(x^3-3*x)",
        ),
        (("a", 1.2),),
    ),
    _Example(
        "Integral definida y Sumas de Riemann",
        "2d",
        (
            "y=4-x^2",
            "integral(4-x^2, 0, 2)",
            "riemann(4-x^2, 0, 2, 8, midpoint)",
        ),
    ),
    _Example(
        "Aproximación de Taylor (Grado 5)",
        "2d",
        ("y=sin(x)", "taylor(sin(x), 0, 5)"),
    ),
    _Example(
        "Curvas e inecuaciones",
        "2d",
        ("x^2+y^2=25", "y>x^2-4 {-2<x<2}"),
    ),
    _Example(
        "Polar y paramétrica",
        "2d",
        ("r=3*cos(3t)", "(4*cos(t), 2*sin(t))"),
    ),
    _Example(
        "Construcción geométrica",
        "2d",
        (
            "A=(-3,0)",
            "B=(3,0)",
            "C=(a,4)",
            "polygon(A,B,C)",
            "midpoint(A,B)",
            "circle(C,2)",
        ),
        (("a", 0.5),),
    ),
    _Example(
        "Datos y recta de ajuste",
        "2d",
        data=((-4, -4.4), (-2, -2.1), (0, 1.1), (2, 2.8), (4, 5.7)),
        regression="linear",
    ),
    _Example(
        "Superficie 3D y Plano Tangente",
        "3d",
        ("z=0.25*(x^2-y^2)", "tangentplane(0.25*(x^2-y^2), 2, 1)"),
    ),
    _Example(
        "Mapa de Contorno y Gradiente 2D",
        "2d",
        ("contour(sin(x)*cos(y))", "gradient(sin(x)*cos(y), 1, 0.5)"),
    ),
)

_TOOLS = (
    ("Punto", "A=(1,2)"),
    ("Segmento", "segment((0,0),(4,3))"),
    ("Recta", "line((0,0),(4,3))"),
    ("Circunferencia", "circle((0,0),3)"),
    ("Polígono", "polygon((0,0),(4,0),(2,3))"),
    ("Punto medio", "midpoint((0,0),(4,3))"),
    ("Distancia", "distance((0,0),(4,3))"),
    ("Intersección de rectas", "intersection((0,0),(4,4),(0,4),(4,0))"),
    ("Intersección de curvas", "intersect(x^2-2, x)"),
    ("Raíces f(x)=0", "roots(x^3-3*x)"),
    ("Extremos locales", "extrema(x^3-3*x)"),
    ("Recta tangente en x₀", "tangent(x^2, 1.5)"),
    ("Recta normal en x₀", "normal(x^2, 1.5)"),
    ("Derivada f'(x)", "derivative(x^3)"),
    ("Integral indefinida", "integral(x^2)"),
    ("Integral definida ∫[a,b]", "integral(4-x^2, 0, 2)"),
    ("Suma de Riemann", "riemann(4-x^2, 0, 2, 8, midpoint)"),
    ("Polinomio de Taylor", "taylor(sin(x), 0, 5)"),
    ("Mapa de contornos 2D", "contour(sin(x)*cos(y))"),
    ("Vector gradiente ∇f", "gradient(x^2+y^2, 1, 1)"),
    ("Plano tangente 3D", "tangentplane(x^2-y^2, 1, 1)"),
)


def _label(text: str, name: str = "graph-note") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _spin(
    name: str,
    value: float,
    minimum: float = -10000.0,
    maximum: float = 10000.0,
) -> QDoubleSpinBox:
    field = QDoubleSpinBox()
    field.setAccessibleName(name)
    field.setDecimals(6)
    field.setRange(minimum, maximum)
    field.setValue(value)
    field.setKeyboardTracking(False)
    field.setMinimumWidth(92)
    return field


class _ExpressionRow(QWidget):
    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, text: str, visible: bool) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.visible = QCheckBox()
        self.visible.setChecked(visible)
        self.visible.setToolTip("Mostrar u ocultar la expresión")
        self.edit = QLineEdit(text)
        self.edit.setObjectName("graph-expression")
        self.edit.setPlaceholderText(
            "Ej. y=a*sin(x), tangent(x^2, 1), riemann(x^2,0,2,8)"
        )
        self.edit.setMaxLength(512)
        self.edit.setMinimumWidth(80)
        self.remove = QPushButton()
        self.remove.setIcon(theme.icon("cancel"))
        self.remove.setFixedWidth(34)
        self.remove.setToolTip("Quitar expresión")
        self.message = _label("", "graph-expression-feedback")
        self.message.setWordWrap(True)
        self.message.setContentsMargins(24, 0, 0, 4)
        self.message.hide()
        controls.addWidget(self.visible)
        controls.addWidget(self.edit, 1)
        controls.addWidget(self.remove)
        layout.addLayout(controls)
        layout.addWidget(self.message)
        self.visible.toggled.connect(self.changed)
        self.edit.textChanged.connect(self.changed)
        self.remove.clicked.connect(lambda: self.remove_requested.emit(self))

    def set_index(self, index: int) -> None:
        position = index + 1
        color = PALETTE[index % len(PALETTE)]
        self.visible.setStyleSheet(f"""
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid
                {color}; border-radius: 8px; background: white; }}
            QCheckBox::indicator:checked {{ background: {color}; }}
            QCheckBox:focus {{ outline: 2px solid {theme.FOCUS}; }}
        """)
        self.visible.setAccessibleName(f"Mostrar expresión {position}")
        self.edit.setAccessibleName(f"Expresión {position}")
        self.remove.setAccessibleName(f"Quitar expresión {position}")

    def feedback(self, error: str, detail: str) -> None:
        self.message.setText(error or detail)
        self.message.setProperty("invalid", bool(error))
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.setVisible(bool(error or detail))
        self.edit.setAccessibleDescription(error or detail)


class _ParameterRow(QWidget):
    changed = Signal(str, float)

    def __init__(self, name: str, value: float) -> None:
        super().__init__()
        self.name = name
        self._anim_step = 1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        self.play_button = QPushButton()
        self.play_button.setCheckable(True)
        self.play_button.setFixedWidth(32)
        self.play_button.setIcon(theme.icon("play", theme.PRIMARY))
        self.play_button.setToolTip(f"Animar parámetro {name}")
        self.play_button.setAccessibleName(f"Animar parámetro {name}")
        caption = _label(f"{name} =", "graph-section")
        caption.setFixedWidth(28)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName(f"Deslizador {name}")
        self.slider.setRange(-100, 100)
        self.slider.setSingleStep(1)
        self.slider.setValue(round(max(-5.0, min(5.0, value)) / 0.05))
        self.field = _spin(f"Valor de {name}", value, -1e12, 1e12)
        self.field.setDecimals(3)
        self.field.setSingleStep(0.05)
        self.field.setFixedWidth(96)
        caption.setBuddy(self.field)
        layout.addWidget(self.play_button)
        layout.addWidget(caption)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.field)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._tick_animation)

        self.play_button.toggled.connect(self._toggle_animation)
        self.slider.valueChanged.connect(self._from_slider)
        self.field.valueChanged.connect(self._from_field)

    def _toggle_animation(self, active: bool) -> None:
        self.play_button.setIcon(
            theme.icon("pause" if active else "play", theme.PRIMARY)
        )
        if active:
            self._anim_timer.start()
        else:
            self._anim_timer.stop()

    def _tick_animation(self) -> None:
        nxt = self.slider.value() + self._anim_step
        if nxt >= self.slider.maximum() or nxt <= self.slider.minimum():
            self._anim_step = -self._anim_step
            nxt = max(self.slider.minimum(), min(self.slider.maximum(), nxt))
        self.slider.setValue(nxt)

    def _from_slider(self, value: int) -> None:
        val_float = round(value * 0.05, 3)
        self.field.blockSignals(True)
        self.field.setValue(val_float)
        self.field.blockSignals(False)
        self.changed.emit(self.name, val_float)

    def _from_field(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round(max(-5.0, min(5.0, value)) / 0.05))
        self.slider.blockSignals(False)
        self.changed.emit(self.name, value)


class _GraphSignals(QObject):
    finished = Signal(int, object)


class _GraphJob(QRunnable):
    def __init__(
        self,
        revision: int,
        session: GraphSession,
        viewport: tuple[tuple[float, float], tuple[float, float]] | None,
    ) -> None:
        super().__init__()
        self.signals = _GraphSignals()
        self.revision = revision
        self.session = session
        self.viewport = viewport

    def run(self) -> None:
        expressions = [text for text, _ in self.session.expressions]
        hidden = {
            index
            for index, (_, visible) in enumerate(self.session.expressions)
            if not visible
        }
        if self.session.data and self.session.mode == "2d":
            pairs = ",".join(f"({x!r},{y!r})" for x, y in self.session.data)
            degree = _FIT_DEGREES.get(self.session.regression)
            expressions.append(
                f"fit({degree},{pairs})" if degree else f"table({pairs})"
            )
        x_range, y_range = self.viewport or (self.session.x_range, self.session.y_range)
        try:
            result = build_graph(
                expressions,
                self.session.parameters,
                x_range=x_range,
                y_range=y_range,
                t_range=self.session.t_range,
                view=self.session.mode,
                hidden_rows=hidden,
            )
        except (ArithmeticError, ValueError, RuntimeError) as exc:
            result = GraphResult(
                errors={-1: f"No se pudo calcular la gráfica ({exc})."},
            )
        try:
            self.signals.finished.emit(self.revision, result)
        except RuntimeError:
            pass


class GraphingWorkspace(QWidget):
    """Estudio gráfico interactivo offline (Síntesis GeoGebra + Desmos)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphing-workspace")
        self.setStyleSheet(_QSS)
        self._expressions: list[_ExpressionRow] = []
        self._parameter_rows: dict[str, _ParameterRow] = {}
        self._parameters: dict[str, float] = {}
        self._last_notable_points: list[dict[str, Any]] = []
        self._running = False
        self._revision = 0
        self._view_revision = 0
        self._updating = False
        self._dirty = False
        self._mode = "2d"
        self._data_feedback = ""
        self._viewport: tuple[tuple[float, float], tuple[float, float]] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(145)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)
        self._build()
        self._apply_example(0)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.addWidget(self._toolbar())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)
        split.addWidget(self._controls())
        split.addWidget(self._plot_panel())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([350, 680])
        layout.addWidget(split, 1)

    def _toolbar(self) -> QWidget:
        toolbar = QFrame()
        toolbar.setObjectName("graph-toolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = _label("Estudio Gráfico (GeoGebra + Desmos)", "graph-title")
        subtitle = _label(
            "Funciones 2D/3D, deslizadores animados, puntos notables, "
            "cálculo simbólico y tablas",
            "graph-subtitle",
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)
        for text, slot in (
            ("Nueva", self._new_session),
            ("Abrir", self._open_session),
            ("Guardar", self._save_session),
            ("PNG", self._export),
            ("Ayuda", self._help),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            layout.addWidget(button)
            if text == "PNG":
                self._export_button = button
                button.setAccessibleName("Exportar gráfica como PNG")
                button.setEnabled(False)
        return toolbar

    def _controls(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("graph-controls")
        panel.setMinimumWidth(285)
        panel.setMaximumWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self._examples = QComboBox()
        self._examples.addItem("Cargar ejemplo interactivo…")
        self._examples.addItems([example.name for example in _EXAMPLES])
        self._examples.setAccessibleName("Ejemplos de graficación")
        self._examples.activated.connect(self._select_example)
        layout.addWidget(self._examples)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._expression_panel(), "Expresiones")
        self._tabs.addTab(self._function_table_panel(), "Tabla f(x)")
        self._tabs.addTab(self._data_panel(), "Datos")
        self._tabs.addTab(self._bounds_panel(), "Escalas")
        layout.addWidget(self._tabs, 1)
        return panel

    def _expression_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(7)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self._add_button = QPushButton("Añadir")
        self._add_button.setIcon(theme.icon("plus", theme.SURFACE))
        self._add_button.setProperty("graphRole", "primary")
        self._add_button.setAccessibleName("Añadir expresión")
        self._add_button.clicked.connect(self._add_empty_expression)
        actions.addWidget(self._add_button)
        self._tools = QComboBox()
        self._tools.addItem("Herramientas GeoGebra / Cálculo…")
        self._tools.addItems([name for name, _ in _TOOLS])
        self._tools.setAccessibleName("Construcciones geométricas y cálculo")
        self._tools.activated.connect(self._insert_tool)
        actions.addWidget(self._tools, 1)
        layout.addLayout(actions)

        self.chk_notable_points = QCheckBox(
            "Destacar puntos notables (raíces, extremos)"
        )
        self.chk_notable_points.setToolTip(
            "Detecta raíces, intersección con el eje Y, extremos locales "
            "e intersecciones entre funciones."
        )
        self.chk_notable_points.setChecked(True)
        self.chk_notable_points.setAccessibleName("Destacar puntos notables")
        self.chk_notable_points.toggled.connect(self._schedule)
        layout.addWidget(self.chk_notable_points)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 2, 2, 2)
        scroll_layout.setSpacing(9)
        self._expression_layout = QVBoxLayout()
        self._expression_layout.setSpacing(6)
        scroll_layout.addLayout(self._expression_layout)
        self._parameter_title = _label(
            "Deslizadores de parámetros (Desmos)", "graph-section"
        )
        self._parameter_title.hide()
        scroll_layout.addWidget(self._parameter_title)
        self._parameter_layout = QVBoxLayout()
        self._parameter_layout.setSpacing(4)
        scroll_layout.addLayout(self._parameter_layout)

        self.notable_card = QFrame()
        self.notable_card.setObjectName("notable-card")
        notable_layout = QVBoxLayout(self.notable_card)
        notable_layout.setContentsMargins(10, 8, 10, 8)
        notable_layout.setSpacing(4)
        notable_header = _label("Inspector de Puntos Notables", "graph-section")
        notable_layout.addWidget(notable_header)
        self.notable_summary_label = _label(
            "Los cortes con ejes, extremos e intersecciones aparecerán aquí.",
            "graph-note",
        )
        self.notable_summary_label.setWordWrap(True)
        self.notable_summary_label.setAccessibleName("Resumen de puntos notables")
        notable_layout.addWidget(self.notable_summary_label)
        scroll_layout.addWidget(self.notable_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        return panel

    def _function_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        intro = _label(
            "Evalúa automáticamente todas las funciones explícitas y=f(x) "
            "en una tabla comparativa."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        self._tbl_start = _spin("Inicio de tabla x", -5.0, -10000.0, 10000.0)
        self._tbl_end = _spin("Fin de tabla x", 5.0, -10000.0, 10000.0)
        self._tbl_step = _spin("Paso de tabla Δx", 1.0, 0.01, 1000.0)
        self._tbl_start.valueChanged.connect(self._refresh_function_table)
        self._tbl_end.valueChanged.connect(self._refresh_function_table)
        self._tbl_step.valueChanged.connect(self._refresh_function_table)
        range_row.addWidget(_label("x₀:"))
        range_row.addWidget(self._tbl_start)
        range_row.addWidget(_label("x₁:"))
        range_row.addWidget(self._tbl_end)
        range_row.addWidget(_label("Δx:"))
        range_row.addWidget(self._tbl_step)
        layout.addLayout(range_row)

        self._func_table = QTableWidget(0, 1)
        self._func_table.setAccessibleName("Tabla de valores de funciones")
        self._func_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._func_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._func_table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self._func_table, 1)

        copy_btn = QPushButton("Copiar tabla de valores")
        copy_btn.setIcon(theme.icon("copy"))
        copy_btn.setAccessibleName("Copiar tabla de valores al portapapeles")
        copy_btn.clicked.connect(self._copy_function_table)
        layout.addWidget(copy_btn)
        return panel

    def _data_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        intro = _label(
            "Añade pares (x, y) para dibujar una nube de puntos y ajustar regresiones."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._data = QTableWidget(0, 2)
        self._data.setAccessibleName("Tabla de coordenadas")
        self._data.setHorizontalHeaderLabels(["x", "y"])
        self._data.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._data.verticalHeader().setDefaultSectionSize(27)
        self._data.setMinimumHeight(70)
        self._data.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._data.itemChanged.connect(self._schedule)
        layout.addWidget(self._data, 1)
        buttons = QHBoxLayout()
        add = QPushButton("Añadir fila")
        add.clicked.connect(self._add_data_row)
        remove = QPushButton("Quitar fila")
        remove.clicked.connect(self._remove_data_row)
        paste = QPushButton("Pegar")
        paste.setAccessibleName("Pegar columnas x e y")
        paste.setToolTip("Pega dos columnas copiadas de una hoja de cálculo")
        paste.clicked.connect(self._paste_data)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(paste)
        layout.addLayout(buttons)
        self._regression = QComboBox()
        self._regression.setAccessibleName("Ajuste estadístico")
        self._regression.addItem("Sin ajuste", "none")
        self._regression.addItem("Regresión lineal", "linear")
        self._regression.addItem("Regresión cuadrática", "quadratic")
        self._regression.addItem("Regresión cúbica", "cubic")
        self._regression.currentIndexChanged.connect(self._schedule)
        layout.addWidget(self._regression)
        self._data_summary = _label("Sin datos")
        self._data_summary.setWordWrap(True)
        layout.addWidget(self._data_summary)
        return panel

    def _bounds_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        note = _label("Los límites de x e y definen la vista y el área de muestreo.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        fields = (
            "Mínimo x",
            "Máximo x",
            "Mínimo y",
            "Máximo y",
            "Mínimo t",
            "Máximo t",
        )
        self._bounds: list[QDoubleSpinBox] = []
        for name, value in zip(fields, (*_X_RANGE, *_Y_RANGE, *_T_RANGE), strict=True):
            field = _spin(name, value)
            field.valueChanged.connect(self._bounds_changed)
            form.addRow(name, field)
            self._bounds.append(field)
        layout.addLayout(form)
        layout.addStretch()
        return panel

    def _plot_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("graph-plot")
        panel.setMinimumWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)
        controls = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode in ("2d", "3d"):
            button = QPushButton(mode.upper())
            button.setCheckable(True)
            button.setProperty("graphRole", "mode")
            button.setAccessibleName(f"Vista {mode.upper()}")
            button.clicked.connect(
                lambda checked, selected=mode: self._set_mode(selected),
            )
            self._mode_group.addButton(button)
            self._mode_buttons[mode] = button
            controls.addWidget(button)
        self._mode_buttons[self._mode].setChecked(True)
        controls.addStretch()
        reset = QPushButton("Restablecer vista")
        reset.clicked.connect(self._reset_bounds)
        controls.addWidget(reset)
        layout.addLayout(controls)
        self._plot = GraphView(workspace=True)
        self._plot.setAccessibleName("Gráfica interactiva")
        self._plot.setMinimumHeight(230)
        self._plot.viewport_changed.connect(self._viewport_changed)
        layout.addWidget(self._plot, 1)
        self._status = _label("Preparando gráfica…", "graph-status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        return panel

    def load_from_solver(
        self, expression: str, module_id: str, variable: str = "x"
    ) -> None:
        """Carga una expresión proveniente del solucionador con análisis automático."""
        expr_clean = expression.strip()
        if not expr_clean:
            return
        target_mode = "2d"
        if module_id == "multivariable":
            target_mode = "3d"
            rows = [
                (f"z={expr_clean}", True),
                (f"tangentplane({expr_clean}, 1, 1)", True),
            ]
        else:
            if variable != "x" and variable.isalpha():
                expr_clean = expr_clean.replace(variable, "x")

            if module_id == "derivatives":
                rows = [
                    (f"y={expr_clean}", True),
                    (f"derivative({expr_clean})", True),
                    (f"tangent({expr_clean}, 1)", True),
                ]
            elif module_id == "integrals":
                rows = [
                    (f"y={expr_clean}", True),
                    (f"integral({expr_clean}, 0, 2)", True),
                    (f"riemann({expr_clean}, 0, 2, 8, midpoint)", False),
                ]
            elif any(op in expr_clean for op in ("<=", ">=", "<", ">")):
                if expr_clean.startswith(("<", ">")):
                    rows = [(f"y {expr_clean}", True)]
                else:
                    rows = [(expr_clean, True)]
            elif module_id == "equations" and "=" in expr_clean:
                lhs, rhs = [p.strip() for p in expr_clean.split("=", 1)]
                rows = [
                    (f"y={lhs}", True),
                    (f"y={rhs}", True),
                    (f"intersect({lhs}, {rhs})", True),
                ]
            else:
                rows = [(f"y={expr_clean}", True)]

        self._apply_session(
            GraphSession(
                expressions=rows,
                parameters={},
                data=[],
                mode=target_mode,
                regression="none",
                x_range=_X_RANGE,
                y_range=_Y_RANGE,
                t_range=_T_RANGE,
            )
        )
        self._tabs.setCurrentIndex(0)

    def _append_expression(
        self,
        text: str = "",
        visible: bool = True,
    ) -> _ExpressionRow:
        row = _ExpressionRow(text, visible)
        row.changed.connect(self._schedule)
        row.remove_requested.connect(self._remove_expression)
        row.set_index(len(self._expressions))
        self._expressions.append(row)
        self._expression_layout.addWidget(row)
        self._sync_expression_controls()
        return row

    def _add_empty_expression(self) -> None:
        if len(self._expressions) < _ROW_LIMIT:
            self._append_expression().edit.setFocus()
            self._schedule()

    @Slot(object)
    def _remove_expression(self, row: _ExpressionRow) -> None:
        self._expressions.remove(row)
        self._expression_layout.removeWidget(row)
        row.deleteLater()
        for index, item in enumerate(self._expressions):
            item.set_index(index)
        self._sync_expression_controls()
        self._schedule()

    def _sync_expression_controls(self) -> None:
        at_capacity = len(self._expressions) >= _ROW_LIMIT
        self._add_button.setEnabled(not at_capacity)
        self._tools.setEnabled(
            not at_capacity
            or any(not row.edit.text().strip() for row in self._expressions),
        )

    def _insert_tool(self, index: int) -> None:
        self._tools.setCurrentIndex(0)
        if index == 0:
            return
        text = _TOOLS[index - 1][1]
        target_mode = "3d" if text.startswith("tangentplane(") else "2d"
        row = next(
            (item for item in self._expressions if not item.edit.text().strip()),
            None,
        )
        if row is None and len(self._expressions) < _ROW_LIMIT:
            row = self._append_expression()
        if row is not None:
            row.visible.setChecked(True)
            row.edit.setText(text)
            row.edit.setFocus()
            self._set_mode(target_mode)
            self._schedule()

    def _set_mode(self, mode: str) -> None:
        self._mode_buttons[mode].setChecked(True)
        if self._mode != mode:
            self._mode = mode
            self._viewport = None
            self._view_revision += 1
            self._schedule()

    def _select_example(self, index: int) -> None:
        self._examples.setCurrentIndex(0)
        if index > 0 and self._can_replace():
            self._apply_example(index - 1)

    def _apply_example(self, index: int) -> None:
        example = _EXAMPLES[index]
        self._apply_session(
            GraphSession(
                expressions=[(text, True) for text in example.expressions],
                parameters=dict(example.parameters),
                data=list(example.data),
                mode=example.mode,
                regression=example.regression,
                x_range=_X_RANGE,
                y_range=_Y_RANGE,
                t_range=_T_RANGE,
            ),
        )
        self._tabs.setCurrentIndex(2 if example.data else 0)

    def _apply_session(self, session: GraphSession) -> None:
        self._updating = True
        for row in tuple(self._expressions):
            self._remove_expression(row)
        for text, visible in session.expressions or [("", True)]:
            self._append_expression(text, visible)
        self._sync_parameters(())
        self._parameters = dict(session.parameters)
        self._set_mode(session.mode)
        self._regression.setCurrentIndex(self._regression.findData(session.regression))
        self._replace_data(session.data)
        values = (*session.x_range, *session.y_range, *session.t_range)
        for field, value in zip(
            self._bounds,
            values,
            strict=True,
        ):
            field.setValue(value)
        self._dirty = False
        self._updating = False
        self._viewport = None
        self._view_revision += 1
        self._queue_render()

    def _replace_data(self, data: list[tuple[float, float]]) -> None:
        self._data.setRowCount(len(data))
        for row, point in enumerate(data):
            for column, value in enumerate(point):
                self._data.setItem(row, column, QTableWidgetItem(str(value)))

    def _add_data_row(self) -> None:
        row = self._data.rowCount()
        if row >= _DATA_LIMIT:
            self._data_summary.setText(f"Máximo de {_DATA_LIMIT} filas.")
            return
        self._data.insertRow(row)
        self._data.setCurrentCell(row, 0)

    def _remove_data_row(self) -> None:
        if self._data.currentRow() >= 0:
            self._data.removeRow(self._data.currentRow())
            self._schedule()

    def _paste_data(self) -> None:
        clipboard = QApplication.clipboard().text().strip()
        if not clipboard:
            return
        lines = clipboard.splitlines()
        if len(lines) + self._data.rowCount() > _DATA_LIMIT:
            self._data_summary.setText(f"Máximo de {_DATA_LIMIT} filas.")
            return
        try:
            points = [self._numeric_point(*line.split("\t")) for line in lines]
        except (TypeError, ValueError):
            self._data_summary.setText(
                "Copia dos columnas numéricas separadas por tabulaciones.",
            )
            return
        start = self._data.rowCount()
        self._updating = True
        self._data.setRowCount(start + len(points))
        for row, point in enumerate(points, start):
            for column, value in enumerate(point):
                self._data.setItem(row, column, QTableWidgetItem(str(value)))
        self._updating = False
        self._schedule()

    @staticmethod
    def _numeric_point(x: str, y: str) -> tuple[float, float]:
        point = float(x.replace(",", ".")), float(y.replace(",", "."))
        if not all(isfinite(value) and abs(value) <= MAX_COORDINATE for value in point):
            raise ValueError("Las coordenadas deben ser números finitos.")
        return point

    def _read_data(self) -> list[tuple[float, float]]:
        data = []
        invalid = []
        for row in range(self._data.rowCount()):
            items = (self._data.item(row, 0), self._data.item(row, 1))
            x, y = (item.text().strip() if item else "" for item in items)
            if not x and not y:
                continue
            try:
                point = self._numeric_point(x, y)
            except ValueError:
                invalid.append(str(row + 1))
                continue
            data.append(point)
        self._data_feedback = (
            f"Filas sin un par numérico válido: {', '.join(invalid)}."
            if invalid
            else ""
        )
        return data

    def _session(self) -> GraphSession:
        xmin, xmax, ymin, ymax, tmin, tmax = [field.value() for field in self._bounds]
        if xmin >= xmax or ymin >= ymax or tmin >= tmax:
            raise ValueError("Cada límite mínimo debe ser menor que su máximo.")
        return GraphSession(
            expressions=[
                (row.edit.text(), row.visible.isChecked()) for row in self._expressions
            ],
            parameters=dict(self._parameters),
            data=self._read_data(),
            mode=self._mode,
            regression=str(self._regression.currentData()),
            x_range=(xmin, xmax),
            y_range=(ymin, ymax),
            t_range=(tmin, tmax),
        )

    def _reset_bounds(self) -> None:
        self._updating = True
        for field, value in zip(
            self._bounds,
            (*_X_RANGE, *_Y_RANGE, *_T_RANGE),
            strict=True,
        ):
            field.setValue(value)
        self._updating = False
        self._bounds_changed()

    def _bounds_changed(self) -> None:
        if self._updating:
            return
        self._viewport = None
        self._view_revision += 1
        self._schedule()

    def _schedule(self) -> None:
        if self._updating:
            return
        self._dirty = True
        self._sync_expression_controls()
        self._queue_render()

    @Slot(object, object)
    def _viewport_changed(
        self,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
    ) -> None:
        self._viewport = x_range, y_range
        self._queue_render()

    def _queue_render(self) -> None:
        self._revision += 1
        self._timer.start()

    @Slot()
    def _render(self) -> None:
        if self._running:
            return
        try:
            session = self._session()
        except ValueError as exc:
            self._status.setText(str(exc))
            self._export_button.setEnabled(False)
            return
        self._running = True
        self._status.setText("Calculando gráfica…")
        self._export_button.setEnabled(False)
        job = _GraphJob(self._revision, session, self._viewport)
        job.signals.finished.connect(self._receive)
        QThreadPool.globalInstance().start(job)

    @Slot(int, object)
    def _receive(self, revision: int, result: GraphResult) -> None:
        self._running = False
        if revision != self._revision:
            self._timer.start()
            return
        session = self._session()
        self._sync_parameters(result.parameters)
        for index, row in enumerate(self._expressions):
            row.feedback(result.errors.get(index, ""), result.details.get(index, ""))
        data_index = len(self._expressions)
        data_summary = self._data_feedback or (
            "La tabla se dibuja en la vista 2D." if session.mode == "3d" else ""
        )
        if not data_summary:
            data_summary = (
                result.errors.get(data_index)
                or result.details.get(data_index)
                or (f"{len(session.data)} puntos" if session.data else "Sin datos")
            )
        self._data_summary.setText(data_summary)

        # Actualizar inspector de puntos notables y su traza superpuesta
        self._last_notable_points = list(result.notable_points)
        traces_to_render = list(result.traces)
        if (
            self.chk_notable_points.isChecked()
            and session.mode == "2d"
            and result.notable_points
        ):
            traces_to_render.append(
                {
                    "type": "scatter",
                    "x": [pt["x"] for pt in result.notable_points],
                    "y": [pt["y"] for pt in result.notable_points],
                    "mode": "markers",
                    "name": "Puntos notables",
                    "text": [
                        f"{pt['label']} · {pt['series']}"
                        for pt in result.notable_points
                    ],
                    "customdata": [
                        {"is_notable": True, "label": pt["label"]}
                        for pt in result.notable_points
                    ],
                    "hoverinfo": "text",
                    "marker": {
                        "size": 8,
                        "color": "#FFFFFF",
                        "line": {"color": theme.TEXT, "width": 2.2},
                    },
                }
            )
            lines = [f"• {pt['label']}" for pt in result.notable_points[:8]]
            if len(result.notable_points) > 8:
                lines.append(f"… y {len(result.notable_points) - 8} punto(s) más.")
            self.notable_summary_label.setText("\n".join(lines))
        elif session.mode == "3d":
            self.notable_summary_label.setText(
                "Vista 3D activa. Usa tangentplane(f(x,y), x₀, y₀) para "
                "inspeccionar el plano tangente y el gradiente."
            )
        else:
            self.notable_summary_label.setText(
                "Sin puntos notables detectados en el intervalo actual."
                if self.chk_notable_points.isChecked()
                else "Detección de puntos notables desactivada."
            )

        self._refresh_function_table()

        self._plot.render_workspace(
            traces_to_render,
            view=session.mode,
            x_range=session.x_range,
            y_range=session.y_range,
            revision=self._view_revision,
        )
        count = len(result.traces)
        notable_count = len(result.notable_points)
        status = (
            f"{count} trazos · {notable_count} puntos notables"
            if count and notable_count and session.mode == "2d"
            else (f"{count} trazos" if count else "Añade una expresión para graficar.")
        )
        if result.errors:
            status = result.errors.get(-1) or (
                f"{count} trazos · Revisa las expresiones o los datos."
            )
        self._status.setText(status)
        self._export_button.setEnabled(bool(count))

    def _refresh_function_table(self) -> None:
        if self._updating:
            return
        expressions = [row.edit.text() for row in self._expressions]
        hidden = {
            idx
            for idx, row in enumerate(self._expressions)
            if not row.visible.isChecked()
        }
        headers, rows = evaluate_function_table(
            expressions,
            self._parameters,
            x_start=self._tbl_start.value(),
            x_end=self._tbl_end.value(),
            step=self._tbl_step.value(),
            hidden_rows=hidden,
        )
        self._func_table.setColumnCount(len(headers))
        self._func_table.setHorizontalHeaderLabels(headers)
        self._func_table.setRowCount(len(rows))
        for r_idx, row_vals in enumerate(rows):
            for c_idx, cell_text in enumerate(row_vals):
                self._func_table.setItem(r_idx, c_idx, QTableWidgetItem(cell_text))

    def _copy_function_table(self) -> None:
        cols = self._func_table.columnCount()
        rows = self._func_table.rowCount()
        if cols == 0 or rows == 0:
            return
        header_cells: list[str] = []
        for c in range(cols):
            h_item = self._func_table.horizontalHeaderItem(c)
            header_cells.append(h_item.text() if h_item is not None else "")
        lines = ["\t".join(header_cells)]
        for r in range(rows):
            row_cells: list[str] = []
            for c in range(cols):
                c_item = self._func_table.item(r, c)
                row_cells.append(c_item.text() if c_item is not None else "")
            lines.append("\t".join(row_cells))
        try:
            QApplication.clipboard().setText("\n".join(lines))
            self._status.setText("Tabla de valores copiada al portapapeles.")
        except Exception:
            self._status.setText("No se pudo copiar al portapapeles.")

    def _sync_parameters(self, names: tuple[str, ...]) -> None:
        if tuple(self._parameter_rows) != names:
            for row in self._parameter_rows.values():
                row._anim_timer.stop()
                self._parameter_layout.removeWidget(row)
                row.deleteLater()
            self._parameter_rows.clear()
            for name in names:
                row = _ParameterRow(name, self._parameters.get(name, 1.0))
                row.changed.connect(self._parameter_changed)
                self._parameter_rows[name] = row
                self._parameter_layout.addWidget(row)
        self._parameter_title.setVisible(bool(names))

    def _parameter_changed(self, name: str, value: float) -> None:
        self._parameters[name] = value
        self._schedule()

    def _can_replace(self) -> bool:
        if not self._dirty:
            return True
        discard = QMessageBox.StandardButton.Discard
        return (
            QMessageBox.warning(
                self,
                "Cambios sin guardar",
                "¿Quieres descartar los cambios de la gráfica actual?",
                discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == discard
        )

    def _new_session(self) -> None:
        if self._can_replace():
            self._apply_session(GraphSession())
            self._tabs.setCurrentIndex(0)
            self._expressions[0].edit.setFocus()

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir gráfica",
            "",
            "Gráfica (*.json)",
        )
        if path and self._can_replace():
            try:
                session = load_graph_session(path)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "No se pudo abrir la gráfica", str(exc))
                return
            self._apply_session(session)
            self._tabs.setCurrentIndex(0 if session.expressions else 2)

    def _save_session(self) -> None:
        try:
            session = self._session()
            if self._data_feedback:
                raise ValueError(self._data_feedback)
        except ValueError as exc:
            QMessageBox.warning(self, "Revisa los datos de la gráfica", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar gráfica",
            "grafica.json",
            "Gráfica (*.json)",
        )
        if path:
            try:
                save_graph_session(path, session)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "No se pudo guardar la gráfica", str(exc))
            else:
                self._dirty = False
                self._status.setText("Gráfica guardada.")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar gráfica",
            "grafica.png",
            "Imagen (*.png)",
        )
        if path:
            self._plot.export_png(path, self._export_error)

    def _export_error(self, error: str) -> None:
        QMessageBox.warning(self, "No se pudo exportar", error)

    def _help(self) -> None:
        QMessageBox.information(
            self,
            "Sintaxis del Estudio Gráfico (GeoGebra + Desmos)",
            "Función y parámetro animado: y=a*sin(x)\n"
            "Recta tangente y normal: tangent(x^3-3*x, 1.2) · normal(x^2, 1)\n"
            "Integral definida y Riemann: integral(4-x^2, 0, 2) · "
            "riemann(4-x^2, 0, 2, 8, midpoint)\n"
            "Polinomio de Taylor: taylor(sin(x), 0, 5)\n"
            "Puntos notables: roots(x^3-3*x) · extrema(x^3-3*x) · "
            "intersect(x^2-2, x)\n"
            "Ecuación implícita e inecuación: x^2+y^2=25 · y>x^2 {-2<x<2}\n"
            "Polar y paramétrica: r=3*cos(3t) · (4*cos(t), 2*sin(t))\n"
            "Contorno y gradiente 2D: contour(sin(x)*cos(y)) · "
            "gradient(x^2+y^2, 1, 1)\n"
            "Superficie 3D y plano tangente: z=x^2-y^2 · "
            "tangentplane(x^2-y^2, 1, 1)\n"
            "Geometría: A=(1,2) · segment(A,(4,3)) · circle(A,3) · "
            "polygon(A,(4,0),(2,3))",
        )
