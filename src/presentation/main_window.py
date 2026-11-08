import datetime
from collections.abc import Callable
from functools import partial
from typing import Any

import sympy as sp
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QResizeEvent,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.domain.errors import StructuredMathError
from src.domain.history import HistoryEntry, HistoryRepository
from src.domain.responses import SolutionResponse
from src.domain.steps import EducationalStep, StepCoverage
from src.infrastructure.parsing.matrix_parser import parse_matrix_input
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter
from src.presentation import theme
from src.presentation.calculation_process_controller import (
    CalculationProcessController,
    ProcessState,
)
from src.presentation.graph_view import GraphView
from src.presentation.history_dialog import HistoryDialog
from src.presentation.math_view import MathView
from src.presentation.matrix_editor import MatrixEditor
from src.presentation.structured_catalog import MATRIX_OPERATIONS
from src.presentation.structured_catalog import MODULES as STRUCTURED_MODULES


def _label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    label.setProperty("role", role)
    if wrap:
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


def _button(text: str, callback: Callable[[], None], name: str) -> QPushButton:
    button = QPushButton(text)
    button.setAccessibleName(name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    button.clicked.connect(callback)
    return button


MODULE_GUIDE = {
    "derivatives": (
        "Encuentra la derivada y estudia las reglas aplicadas.",
        "x^2 + 3x",
    ),
    "integrals": ("Encuentra una antiderivada y revisa el procedimiento.", "sin(x)"),
    "equations": (
        "Resuelve una ecuación y revisa cómo se despeja la incógnita.",
        "x^2=4",
    ),
    "multivariable": (
        "Calcula derivadas parciales, gradiente ∇f, laplaciano ∇²f, "
        "derivada direccional y valor en un punto.",
        "x^2*y + y^3",
    ),
}


class MainWindow(QMainWindow):
    def __init__(
        self, solve_use_case: Any, history_repo: HistoryRepository, parser: MathParser
    ) -> None:
        super().__init__()
        self.solve_use_case = solve_use_case
        self.history_repo = history_repo
        self.parser = parser
        self.adapter = SympyAdapter()
        self.current_module_id = "derivatives"
        self._active_request: tuple[str, str, dict[str, Any]] | None = None
        self._state = ProcessState.IDLE
        self._input_valid = False
        self._response: SolutionResponse | None = None
        self._graph_data: list[dict[str, Any]] = []
        self.graph_view: GraphView | None = None
        self._graph_workspace: QWidget | None = None
        self.setWindowTitle("Calculadora Súper Inteligente")
        self.setMinimumSize(820, 600)
        self.resize(1180, 760)
        self.worker_controller = CalculationProcessController(timeout_ms=15000)
        self.worker_controller.finished_calculation.connect(self._on_solve_finished)
        self.worker_controller.error_occurred.connect(self._on_solve_error)
        self.worker_controller.state_changed.connect(self._on_controller_state_changed)
        self._setup_ui()

    def _setup_ui(self) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        top = QFrame()
        top.setObjectName("top-bar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(24, 8, 24, 8)
        mark = QLabel()
        mark.setPixmap(theme.icon("calculator", theme.PRIMARY).pixmap(28, 28))
        top_layout.addWidget(mark)
        self.brand = _label("Calculadora Súper Inteligente")
        self.brand.setObjectName("brand")
        top_layout.addWidget(self.brand)
        top_layout.addStretch()
        self.btn_new = _button(
            "Nueva resolución", self._new_resolution, "Nueva resolución"
        )
        self.btn_new.setObjectName("btn-new")
        self.btn_new.setIcon(theme.icon("plus", theme.PRIMARY))
        top_layout.addWidget(self.btn_new)
        shell_layout.addWidget(top)
        body = QHBoxLayout()
        body.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        nav = QVBoxLayout(self.sidebar)
        nav.setContentsMargins(8, 8, 8, 8)
        nav.setSpacing(2)
        nav.addWidget(_label("Cálculo", "nav-group"))
        self.btn_derivadas = self._nav_button("Derivadas", "derivatives", "derivative")
        self.btn_integrales = self._nav_button("Integrales", "integrals", "integral")
        self.btn_multivariable = self._nav_button(
            "Multivariable", "multivariable", "multivariable"
        )
        nav.addWidget(self.btn_derivadas)
        nav.addWidget(self.btn_integrales)
        nav.addWidget(self.btn_multivariable)
        self.structured_nav: dict[str, QPushButton] = {}
        for module_id in ("definite_integrals", "vector_calculus", "ode"):
            nav.addWidget(self._structured_nav_button(module_id))
        nav.addWidget(_label("Álgebra", "nav-group"))
        self.btn_ecuaciones = self._nav_button("Ecuaciones", "equations", "equation")
        nav.addWidget(self.btn_ecuaciones)
        nav.addWidget(self._structured_nav_button("matrices"))
        nav.addWidget(self._structured_nav_button("discrete"))
        nav.addWidget(_label("Geometría", "nav-group"))
        nav.addWidget(self._structured_nav_button("geometry"))
        nav.addWidget(self._structured_nav_button("analytic_geometry"))
        self.btn_graficadora = self._nav_button("Graficadora", "graphing", "graph")
        nav.addWidget(_label("Herramientas", "nav-group"))
        nav.addWidget(self.btn_graficadora)
        self.btn_historial = _button(
            "Historial", self._open_history, "Abrir historial local"
        )
        self.btn_historial.setProperty("role", "nav")
        self.btn_historial.setIcon(theme.icon("history"))
        nav.addWidget(self.btn_historial)
        nav.addStretch()
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("sidebar-scroll")
        self.sidebar_scroll.setFixedWidth(theme.SIDEBAR_WIDTH)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.sidebar_scroll.setWidget(self.sidebar)
        body.addWidget(self.sidebar_scroll)
        self.work_scroll = QScrollArea()
        self.work_scroll.setWidgetResizable(True)
        self.work_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        work = QWidget()
        work.setObjectName("work-content")
        self.work_layout = QVBoxLayout(work)
        self.work_layout.setContentsMargins(24, 16, 24, 24)
        self.work_layout.setSpacing(16)
        self.title_label = _label("Derivadas")
        self.title_label.setObjectName("module-title")
        self.work_layout.addWidget(self.title_label)
        self.module_subtitle = _label(
            MODULE_GUIDE["derivatives"][0], "module-subtitle", True
        )
        self.work_layout.addWidget(self.module_subtitle)
        self._setup_input()
        self._setup_response()
        self.empty_state = _label(
            "Aquí aparecerán el resultado y el procedimiento.", "empty-state", True
        )
        self.work_layout.addWidget(self.empty_state)
        self._setup_shortcuts()
        self.work_layout.addStretch()
        self.work_scroll.setWidget(work)
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(self.work_scroll)
        body.addWidget(self.workspace_stack, 1)
        shell_layout.addLayout(body, 1)
        footer = QWidget()
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(24, 4, 24, 6)
        foot.addWidget(_label("Guardado localmente · Funciona sin conexión", "muted"))
        foot.addStretch()
        shell_layout.addWidget(footer)
        self.parse_timer = QTimer(self)
        self.parse_timer.setSingleShot(True)
        self.parse_timer.setInterval(300)
        self.parse_timer.timeout.connect(self._detect_variables)
        self._apply_stylesheet()
        self.btn_derivadas.setChecked(True)
        self.input_editor.setFocus()
        focus_order = [
            self.btn_derivadas,
            self.btn_integrales,
            self.btn_multivariable,
            *(self.structured_nav[key] for key in
              ("definite_integrals", "vector_calculus", "ode")),
            self.btn_ecuaciones,
            *(self.structured_nav[key] for key in
              ("matrices", "discrete", "geometry", "analytic_geometry")),
            self.btn_graficadora,
            self.btn_historial,
            self.btn_new,
            self.structured_op_combo,
            self.btn_example,
            self.input_editor,
            self.var_combo,
            self.order_spin,
            self.btn_solve,
            self.btn_cancel,
            self.btn_toggle_keyboard,
            *self.keyboard_widget.findChildren(QPushButton),
            self.btn_copy,
            self.btn_copy_latex,
            self.tabs,
        ]
        for first, second in zip(focus_order, focus_order[1:]):
            QWidget.setTabOrder(first, second)

    def _setup_shortcuts(self) -> None:
        self._solver_shortcuts: list[QShortcut] = []
        for keys, action in (
            ("Ctrl+Return", self._on_solve),
            ("Ctrl+Enter", self._on_solve),
            ("Ctrl+L", self._focus_expression),
            ("Ctrl+N", self._new_resolution),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(action)
            self._solver_shortcuts.append(shortcut)
        history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        history_shortcut.setAutoRepeat(False)
        history_shortcut.activated.connect(self._open_history)
        graph_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        graph_shortcut.setAutoRepeat(False)
        graph_shortcut.activated.connect(self._open_graph_workspace)

    def _focus_expression(self) -> None:
        self.work_scroll.ensureWidgetVisible(self.input_editor)
        self.input_editor.setFocus()

    def _nav_button(self, title: str, module_id: str, symbol: str) -> QPushButton:
        button = _button(title, lambda: self._switch_module(module_id), title)
        button.setCheckable(True)
        button.setProperty("role", "nav")
        button.setIcon(theme.icon(symbol, theme.PRIMARY))
        button.setIconSize(QSize(20, 20))
        return button

    def _structured_nav_button(self, module_id: str) -> QPushButton:
        module = STRUCTURED_MODULES[module_id]
        button = self._nav_button(module.navigation, module_id, module.icon)
        button.setAccessibleName(module.title)
        button.setToolTip(module.title)
        self.structured_nav[module_id] = button
        return button

    def _setup_input(self) -> None:
        card = QFrame()
        card.setObjectName("input-card")
        self.input_layout = QVBoxLayout(card)
        layout = self.input_layout
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        self.structured_controls = QWidget()
        operation_row = QHBoxLayout(self.structured_controls)
        operation_row.setContentsMargins(0, 0, 0, 4)
        operation_label = _label("Operación")
        self.structured_op_combo = QComboBox()
        self.structured_op_combo.setAccessibleName("Operación matemática")
        operation_label.setBuddy(self.structured_op_combo)
        self.structured_op_combo.currentIndexChanged.connect(
            self._update_structured_guide
        )
        self.btn_example = _button("Usar ejemplo", self._use_example, "Usar ejemplo")
        operation_row.addWidget(operation_label)
        operation_row.addWidget(self.structured_op_combo, 1)
        operation_row.addWidget(self.btn_example)
        self.structured_controls.hide()
        layout.addWidget(self.structured_controls)
        self._setup_matrix_editor(layout)
        expression_label = _label("Expresión", "section")
        layout.addWidget(expression_label)
        self.input_editor = QTextEdit()
        self.input_editor.setAcceptRichText(False)
        self.input_editor.setTabChangesFocus(True)
        self.input_editor.setFixedHeight(52)
        self.input_editor.setPlaceholderText(
            "Ejemplo: " + MODULE_GUIDE["derivatives"][1]
        )
        self.input_editor.setAccessibleName("Expresión matemática")
        self.input_editor.setAccessibleDescription(
            "Escribe una expresión y revisa su interpretación antes de resolver."
        )
        expression_label.setBuddy(self.input_editor)
        self.input_editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input_editor)
        layout.addWidget(
            _label(
                "Ctrl+Enter para resolver · Ctrl+L para volver a la expresión",
                "muted",
                True,
            )
        )
        preview_row = QHBoxLayout()
        preview_row.addWidget(_label("Interpretamos:"))
        self.interpretation_label = _label("—", wrap=True)
        self.interpretation_label.setObjectName("interpretation")
        self.interpretation_label.setAccessibleName("Interpretación matemática")
        preview_row.addWidget(self.interpretation_label, 1)
        layout.addLayout(preview_row)
        self.interpretation_math = MathView()
        self.interpretation_math.setObjectName("interpretation-math")
        self.interpretation_math.setAccessibleName("Previsualización de fórmula")
        self.interpretation_math.setFixedHeight(54)
        self.interpretation_math.hide()
        layout.addWidget(self.interpretation_math)
        self.error_preview_label = _label("", "error", True)
        self.error_preview_label.setAccessibleName("Error de entrada")
        self.error_preview_label.hide()
        layout.addWidget(self.error_preview_label)
        self.mv_widget = QWidget()
        mv_grid = QGridLayout(self.mv_widget)
        mv_grid.setContentsMargins(0, 0, 0, 0)
        mv_grid.setHorizontalSpacing(12)
        mv_grid.setVerticalSpacing(4)
        self.mv_op_label = _label("Operación")
        self.mv_op_combo = QComboBox()
        self.mv_op_combo.setAccessibleName("Operación multivariable")
        for label, value in (
            ("Derivada parcial (∂f/∂x)", "partial"),
            ("Gradiente (∇f)", "gradient"),
            ("Laplaciano (∇²f)", "laplacian"),
            ("Derivada direccional (Dᵤf)", "directional"),
            ("Evaluar en punto f(P)", "multivariable_value"),
        ):
            self.mv_op_combo.addItem(label, value)
        self.mv_op_combo.currentIndexChanged.connect(self._sync_multivariable_controls)
        self.mv_vars_label = _label("Variables")
        self.mv_vars_edit = QLineEdit("x, y")
        self.mv_vars_edit.setAccessibleName("Variables independientes")
        self.mv_point_label = _label("Punto P")
        self.mv_point_edit = QLineEdit("1, 2")
        self.mv_point_edit.setAccessibleName("Punto de evaluación")
        self.mv_dir_label = _label("Dirección u")
        self.mv_dir_edit = QLineEdit("1, 0")
        self.mv_dir_edit.setAccessibleName("Vector dirección")
        mv_grid.addWidget(self.mv_op_label, 0, 0)
        mv_grid.addWidget(self.mv_op_combo, 1, 0)
        mv_grid.addWidget(self.mv_vars_label, 0, 1)
        mv_grid.addWidget(self.mv_vars_edit, 1, 1)
        mv_grid.addWidget(self.mv_point_label, 0, 2)
        mv_grid.addWidget(self.mv_point_edit, 1, 2)
        mv_grid.addWidget(self.mv_dir_label, 0, 3)
        mv_grid.addWidget(self.mv_dir_edit, 1, 3)
        self.mv_widget.hide()
        layout.addWidget(self.mv_widget)
        self.params_layout = QGridLayout()
        self.params_layout.setHorizontalSpacing(16)
        self.params_layout.setVerticalSpacing(4)
        self.var_label = _label("Variable")
        self.var_combo = QComboBox()
        self.var_combo.addItems(["x"])
        self.var_combo.setMinimumWidth(90)
        self.var_combo.setAccessibleName("Variable")
        self.var_label.setBuddy(self.var_combo)
        self.order_label = _label("Orden")
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 5)
        self.order_spin.setAccessibleName("Orden de derivación")
        self.order_label.setBuddy(self.order_spin)
        self.params_layout.addWidget(self.var_label, 0, 0)
        self.params_layout.addWidget(self.var_combo, 1, 0)
        self.params_layout.addWidget(self.order_label, 0, 1)
        self.params_layout.addWidget(self.order_spin, 1, 1)
        self.action_bar = QWidget()
        actions = QGridLayout(self.action_bar)
        self.actions_layout = actions
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.setColumnStretch(0, 1)
        self.btn_solve = _button("Resolver", self._on_solve, "Resolver expresión")
        self.btn_solve.setObjectName("btn-solve")
        self.btn_solve.setIcon(theme.icon("solve", theme.SURFACE))
        self.btn_solve.setEnabled(False)
        self.btn_solve.setFixedWidth(130)
        actions.addWidget(self.btn_solve, 0, 1)
        self.btn_cancel = _button("Cancelar", self._on_cancel, "Cancelar cálculo")
        self.btn_cancel.setObjectName("btn-cancel")
        self.btn_cancel.setFixedWidth(130)
        self.btn_cancel.setIcon(theme.icon("cancel", theme.DANGER))
        self.btn_cancel.hide()
        actions.addWidget(self.btn_cancel, 0, 2)
        self.btn_toggle_keyboard = _button(
            "Teclado matemático ▾", self._toggle_keyboard, "Teclado matemático"
        )
        self.btn_toggle_keyboard.setObjectName("btn-keyboard")
        self.btn_toggle_keyboard.setAccessibleDescription("Teclado cerrado.")
        self.btn_toggle_keyboard.setCheckable(True)
        actions.addWidget(self.btn_toggle_keyboard, 0, 3)
        self.params_layout.addWidget(self.action_bar, 1, 2)
        self.params_layout.setColumnStretch(2, 1)
        layout.addLayout(self.params_layout)
        self.status_label = _label(
            "Escribe una expresión válida para resolver.", "muted", True
        )
        self.status_label.setAccessibleName("Estado de la resolución")
        layout.addWidget(self.status_label)
        self.keyboard_widget = QWidget()
        self.keyboard_widget.setObjectName("math-keyboard")
        keyboard = QVBoxLayout(self.keyboard_widget)
        keyboard.setContentsMargins(0, 4, 0, 0)
        key_names = {
            "DEL": "Borrar selección o carácter anterior",
            "AC": "Limpiar expresión",
            "abs()": "Insertar valor absoluto",
            "pi": "Insertar constante pi",
            "e": "Insertar constante e",
        }
        keys = [
            ["sin()", "cos()", "tan()", "ln()", "sqrt()", "abs()", "pi", "e"],
            ["7", "8", "9", "(", ")", "^", "/"],
            ["4", "5", "6", "*", "-", "+", "="],
            ["1", "2", "3", "0", ".", "x", "DEL", "AC"],
        ]
        for values in keys:
            row = QHBoxLayout()
            for key in values:
                button = _button(
                    key,
                    partial(self._on_keyboard_key, key),
                    key_names.get(key, f"Insertar {key}"),
                )
                button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
                row.addWidget(button, 1)
            keyboard.addLayout(row)
        self.keyboard_widget.hide()
        layout.addWidget(self.keyboard_widget)
        self.work_layout.addWidget(card)

    def _setup_matrix_editor(self, layout: QVBoxLayout) -> None:
        self.matrix_controls = QWidget()
        controls = QVBoxLayout(self.matrix_controls)
        controls.setContentsMargins(0, 0, 0, 4)
        options = QGridLayout()
        self.btn_matrix_editor = _button(
            "Cuadrículas A/B", self._toggle_matrix_editor, "Mostrar cuadrículas A y B"
        )
        self.btn_matrix_editor.setCheckable(True)
        options.addWidget(self.btn_matrix_editor, 0, 0)
        self.matrix_decimal = QCheckBox("Mostrar decimales")
        self.matrix_decimal.toggled.connect(self._matrix_options_changed)
        options.addWidget(self.matrix_decimal, 1, 0, 1, 2)
        self.matrix_precision = QSpinBox()
        self.matrix_precision.setRange(2, 15)
        self.matrix_precision.setValue(8)
        self.matrix_precision.setSuffix(" cifras")
        self.matrix_precision.setAccessibleName("Cifras significativas")
        self.matrix_precision.valueChanged.connect(self._matrix_options_changed)
        options.addWidget(self.matrix_precision, 1, 2)
        self.matrix_method = QComboBox()
        self.matrix_method.setAccessibleName("Método del determinante")
        for label, identifier in (
            ("Determinante automático", "auto"),
            ("Cofactores por fila", "row"),
            ("Cofactores por columna", "column"),
            ("Reducción por filas", "elimination"),
        ):
            self.matrix_method.addItem(label, identifier)
        self.matrix_method.currentIndexChanged.connect(self._matrix_options_changed)
        options.addWidget(self.matrix_method, 2, 0, 1, 2)
        self.matrix_index = QSpinBox()
        self.matrix_index.setRange(1, 8)
        self.matrix_index.setAccessibleName("Número de fila o columna para cofactores")
        self.matrix_index.valueChanged.connect(self._matrix_options_changed)
        options.addWidget(self.matrix_index, 2, 2)
        self.matrix_argument = QLineEdit("2")
        self.matrix_argument.setAccessibleName("Factor o exponente de la matriz")
        options.addWidget(self.matrix_argument, 3, 0, 1, 3)
        controls.addLayout(options)
        self.matrix_editor = MatrixEditor()
        self.matrix_editor.use_grids.connect(self._apply_matrix_grids)
        self.matrix_editor.operation_requested.connect(self._solve_matrix_grids)
        self.matrix_editor.hide()
        controls.addWidget(self.matrix_editor)
        self.matrix_controls.hide()
        layout.addWidget(self.matrix_controls)

    def _toggle_matrix_editor(self) -> None:
        self.matrix_editor.setVisible(self.btn_matrix_editor.isChecked())

    def _matrix_options_changed(self) -> None:
        determinant = self.structured_op_combo.currentData() == "determinant"
        self.matrix_method.setVisible(determinant)
        self.matrix_index.setVisible(
            determinant and self.matrix_method.currentData() in {"row", "column"}
        )
        self.matrix_precision.setVisible(self.matrix_decimal.isChecked())
        if self._response and self.current_module_id == "matrices":
            self.result_title.setText("Resultado anterior")

    def _apply_matrix_grids(self) -> None:
        kind = MATRIX_OPERATIONS[self.structured_op_combo.currentData()].input_kind
        a = self.matrix_editor.a.text()
        b = self.matrix_editor.b.text()
        if kind == "expression":
            self.matrix_editor.feedback.setText(
                "A y B se aplicarán al resolver la expresión."
            )
            self._focus_expression()
            return
        active = self.matrix_editor.tabs.currentWidget()
        operand = b if active is self.matrix_editor.b else a
        if kind == "argument":
            operand = f"[{operand}, {self.matrix_argument.text()}]"
        elif kind == "binary":
            operand = f"[{a}, {b}]"
        self.input_editor.setPlainText(operand)
        self.matrix_editor.feedback.setText("Cuadrículas enviadas al editor.")
        self._detect_variables()

    def _solve_matrix_grids(self, operation: str) -> None:
        if self.current_module_id != "matrices" or self._state != ProcessState.IDLE:
            return
        index = self.structured_op_combo.findData(operation)
        if index < 0:
            return
        self.structured_op_combo.setCurrentIndex(index)
        self._apply_matrix_grids()
        self._on_solve()

    def _setup_response(self) -> None:
        self.response_card = QFrame()
        self.response_card.setObjectName("response-card")
        layout = QVBoxLayout(self.response_card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.summary = QFrame()
        self.summary.setObjectName("summary")
        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(16, 10, 16, 10)
        summary_layout.setSpacing(4)
        heading = QHBoxLayout()
        self.summary_heading = heading
        self.result_title = _label("Resultado", "section")
        self.result_title.setObjectName("result-title")
        heading.addWidget(self.result_title, 1)
        self.btn_copy = _button(
            "Copiar", lambda: self._copy_result(False), "Copiar resultado"
        )
        self.btn_copy.setIcon(theme.icon("copy"))
        self.btn_copy_latex = _button(
            "Copiar LaTeX",
            lambda: self._copy_result(True),
            "Copiar resultado como LaTeX",
        )
        self.btn_open_in_graph = _button(
            "Abrir en Graficadora",
            self._send_to_graph_workspace,
            "Abrir expresión en la graficadora",
        )
        self.btn_open_in_graph.setIcon(theme.icon("graph", theme.PRIMARY))
        copy_actions = QWidget()
        self.copy_layout = QGridLayout(copy_actions)
        self.copy_layout.setContentsMargins(0, 0, 0, 0)
        self.copy_layout.setSpacing(6)
        self.copy_layout.addWidget(self.btn_copy, 0, 0)
        self.copy_layout.addWidget(self.btn_copy_latex, 0, 1)
        self.copy_layout.addWidget(self.btn_open_in_graph, 0, 2)
        heading.addWidget(copy_actions)
        summary_layout.addLayout(heading)
        self.result_math = MathView()
        self.result_math.setProperty("math_size", theme.RESULT_FONT_SIZE)
        self.result_math.setFixedHeight(64)
        self.result_math.setAccessibleName("Resultado matemático")
        self.result_reading_layout = QHBoxLayout()
        self.result_reading_layout.addWidget(self.result_math, 3)
        self.verification_label = _label("", "success", True)
        self.result_reading_layout.addWidget(self.verification_label, 2)
        summary_layout.addLayout(self.result_reading_layout)
        layout.addWidget(self.summary)
        self.notices = _label("", "warning", True)
        layout.addWidget(self.notices)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Detalles de la resolución")
        self.tabs.setMinimumHeight(260)
        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.result_content = QWidget()
        self.result_layout = QVBoxLayout(self.result_content)
        self.result_layout.setContentsMargins(8, 4, 8, 4)
        self.result_layout.setSpacing(0)
        self.result_layout.addStretch()
        self.result_area.setWidget(self.result_content)
        self.tabs.addTab(self.result_area, "Procedimiento")
        self.graph_page = QWidget()
        self.graph_layout = QVBoxLayout(self.graph_page)
        self.graph_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs.addTab(self.graph_page, "Gráfica")
        self.check_label = _label("", wrap=True)
        check_page = QWidget()
        check_layout = QVBoxLayout(check_page)
        check_layout.addWidget(self.check_label)
        check_layout.addStretch()
        self.tabs.addTab(check_page, "Comprobación")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)
        self.response_card.hide()
        self.work_layout.addWidget(self.response_card)

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(theme.QSS)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "params_layout"):
            return
        compact = self.width() < 1000
        self.brand.setText(
            "Calculadora" if compact else "Calculadora Súper Inteligente"
        )
        self.work_layout.setContentsMargins(
            16 if compact else 24, 12, 16 if compact else 24, 16
        )
        direction = (
            QBoxLayout.Direction.TopToBottom
            if compact
            else QBoxLayout.Direction.LeftToRight
        )
        if hasattr(self, "summary_heading"):
            self.summary_heading.setDirection(direction)
        if hasattr(self, "copy_layout"):
            self.copy_layout.removeWidget(self.btn_open_in_graph)
            if compact:
                self.copy_layout.addWidget(self.btn_open_in_graph, 1, 0, 1, 2)
            else:
                self.copy_layout.addWidget(self.btn_open_in_graph, 0, 2)
        if hasattr(self, "result_reading_layout"):
            self.result_reading_layout.setDirection(direction)
        self._layout_input_actions()

    def _layout_input_actions(self) -> None:
        margins = (
            self.work_layout.contentsMargins() + self.input_layout.contentsMargins()
        )
        available = (
            self.width()
            - self.sidebar_scroll.width()
            - self.work_scroll.verticalScrollBar().sizeHint().width()
            - margins.left()
            - margins.right()
            - 2  # Borde de la tarjeta.
        )
        self.actions_layout.addWidget(self.btn_toggle_keyboard, 0, 3)
        if self.actions_layout.minimumSize().width() > available:
            self.actions_layout.addWidget(
                self.btn_toggle_keyboard, 1, 1, 1, 3, Qt.AlignmentFlag.AlignRight
            )
        self.params_layout.addWidget(self.action_bar, 1, 2)
        if self.width() < 1000 or self.params_layout.minimumSize().width() > available:
            self.params_layout.addWidget(self.action_bar, 2, 0, 1, 3)

    def _toggle_keyboard(self) -> None:
        opened = self.btn_toggle_keyboard.isChecked()
        self.keyboard_widget.setVisible(opened)
        self.btn_toggle_keyboard.setText(
            "Teclado matemático ▴" if opened else "Teclado matemático ▾"
        )
        self.btn_toggle_keyboard.setAccessibleDescription(
            "Teclado abierto." if opened else "Teclado cerrado."
        )
        if opened:
            QTimer.singleShot(0, self, self._reveal_keyboard)

    def _reveal_keyboard(self) -> None:
        if self.keyboard_widget.isVisible():
            self.work_scroll.ensureWidgetVisible(self.keyboard_widget, 0, 8)
            self.work_scroll.ensureWidgetVisible(self.action_bar, 0, 8)

    def _on_keyboard_key(self, key: str) -> None:
        focused = QApplication.focusWidget()
        if focused is None or not self.keyboard_widget.isAncestorOf(focused):
            self.input_editor.setFocus()
        cursor = self.input_editor.textCursor()
        if key == "DEL":
            cursor.deletePreviousChar()
        elif key == "AC":
            self.input_editor.clear()
            self._detect_variables()
        else:
            cursor.insertText(key)
            if key.endswith("()"):
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.input_editor.setTextCursor(cursor)

    def _new_resolution(self) -> None:
        if self._state != ProcessState.IDLE:
            return
        self._clear_results()
        self._active_request = None
        self.input_editor.clear()
        self.order_spin.setValue(1)
        self._detect_variables()
        self.work_scroll.verticalScrollBar().setValue(0)
        self.input_editor.setFocus()

    def _switch_module(self, module_id: str) -> None:
        if self._state != ProcessState.IDLE:
            return
        if module_id == "graphing":
            self._open_graph_workspace()
            return
        titles = {
            "derivatives": "Derivadas",
            "integrals": "Integrales",
            "equations": "Ecuaciones",
            "multivariable": "Cálculo Multivariable",
            **{key: module.title for key, module in STRUCTURED_MODULES.items()},
        }
        if module_id not in titles:
            return
        returning = self.workspace_stack.currentWidget() is not self.work_scroll
        self.workspace_stack.setCurrentWidget(self.work_scroll)
        self.btn_new.show()
        self.btn_graficadora.setChecked(False)
        for shortcut in self._solver_shortcuts:
            shortcut.setEnabled(True)
        if returning and module_id == self.current_module_id:
            self._solver_navigation(module_id)
            self._focus_expression()
            return
        changed_module = self.current_module_id != module_id
        self.current_module_id = module_id
        self.title_label.setText(titles[module_id])
        structured = STRUCTURED_MODULES.get(module_id)
        self.structured_controls.setVisible(structured is not None)
        self.matrix_controls.setVisible(module_id == "matrices")
        if structured is None:
            description, example = MODULE_GUIDE[module_id]
            self.module_subtitle.setText(description)
            self.input_editor.setPlaceholderText(f"Ejemplo: {example}")
        else:
            if changed_module:
                self.structured_op_combo.clear()
                for key, operation in structured.operations.items():
                    self.structured_op_combo.addItem(operation.name, key)
            self._update_structured_guide()
        self._solver_navigation(module_id)
        self._sync_multivariable_controls()
        self._layout_input_actions()
        self._clear_results()
        self._detect_variables()

    def _update_structured_guide(self) -> None:
        module = STRUCTURED_MODULES.get(self.current_module_id)
        if module is None:
            return
        operation = module.operations.get(self.structured_op_combo.currentData())
        if operation is None:
            return
        self.module_subtitle.setText(operation.instruction)
        self.input_editor.setPlaceholderText(f"Ejemplo: {operation.example}")
        if self.current_module_id == "matrices":
            self.matrix_argument.setVisible(operation.input_kind == "argument")
            self.matrix_argument.setPlaceholderText(
                "Exponente" if self.structured_op_combo.currentData() == "power"
                else "Factor de escala"
            )
            self._matrix_options_changed()
        if self._response:
            self.result_title.setText("Resultado anterior")

    def _use_example(self) -> None:
        module = STRUCTURED_MODULES[self.current_module_id]
        operation = module.operations[self.structured_op_combo.currentData()]
        if self.current_module_id == "matrices":
            argument = self.matrix_editor.load_example(
                operation.example, operation.input_kind
            )
            if argument is not None:
                self.matrix_argument.setText(argument)
        self.input_editor.setPlainText(operation.example)
        self._detect_variables()
        self._focus_expression()

    def _sync_multivariable_controls(self) -> None:
        if self.current_module_id != "multivariable":
            self.mv_widget.hide()
            scalar = self.current_module_id not in STRUCTURED_MODULES
            self.var_label.setVisible(scalar)
            self.var_combo.setVisible(scalar)
            is_deriv = self.current_module_id == "derivatives"
            self.order_spin.setVisible(is_deriv)
            self.order_label.setVisible(is_deriv)
            return
        self.mv_widget.show()
        op = str(self.mv_op_combo.currentData() or "partial")
        is_partial = op == "partial"
        needs_point = op in ("directional", "multivariable_value")
        needs_dir = op == "directional"
        self.var_label.setVisible(is_partial)
        self.var_combo.setVisible(is_partial)
        self.order_label.setVisible(is_partial)
        self.order_spin.setVisible(is_partial)
        self.mv_vars_label.setVisible(not is_partial)
        self.mv_vars_edit.setVisible(not is_partial)
        self.mv_point_label.setVisible(needs_point)
        self.mv_point_edit.setVisible(needs_point)
        self.mv_dir_label.setVisible(needs_dir)
        self.mv_dir_edit.setVisible(needs_dir)

    def _solver_navigation(self, module_id: str) -> None:
        self.btn_derivadas.setChecked(module_id == "derivatives")
        self.btn_integrales.setChecked(module_id == "integrals")
        self.btn_multivariable.setChecked(module_id == "multivariable")
        self.btn_ecuaciones.setChecked(module_id == "equations")
        for key, button in self.structured_nav.items():
            button.setChecked(module_id == key)

    def _open_graph_workspace(self) -> None:
        if self._graph_workspace is None:
            from src.presentation.graphing_workspace import GraphingWorkspace

            self._graph_workspace = GraphingWorkspace()
            self.workspace_stack.addWidget(self._graph_workspace)
        self.workspace_stack.setCurrentWidget(self._graph_workspace)
        self.btn_new.hide()
        for shortcut in self._solver_shortcuts:
            shortcut.setEnabled(False)
        self._solver_navigation("")
        self.btn_graficadora.setChecked(True)

    def _send_to_graph_workspace(self) -> None:
        self._open_graph_workspace()
        expr_text = self.input_editor.toPlainText().strip()
        workspace = self._graph_workspace
        if expr_text and workspace is not None:
            loader = getattr(workspace, "load_from_solver", None)
            if callable(loader):
                loader(
                    expr_text,
                    self.current_module_id,
                    self.var_combo.currentText(),
                )

    def _open_history(self) -> None:
        if self._state != ProcessState.IDLE:
            return
        dialog = HistoryDialog(self.history_repo, self)
        if dialog.exec() == HistoryDialog.DialogCode.Accepted and dialog.selected_entry:
            entry = dialog.selected_entry
            self._switch_module(entry.module_id)
            self.input_editor.setPlainText(entry.original_input)
            self._detect_variables()
            if entry.parameters:
                self.var_combo.setCurrentText(entry.parameters.get("variable", "x"))
                self.order_spin.setValue(entry.parameters.get("order", 1))
                if entry.module_id in STRUCTURED_MODULES:
                    idx = self.structured_op_combo.findData(
                        entry.parameters.get("operation")
                    )
                    if idx >= 0:
                        self.structured_op_combo.setCurrentIndex(idx)
                if entry.module_id == "matrices":
                    method = self.matrix_method.findData(
                        entry.parameters.get("method", "auto")
                    )
                    self.matrix_method.setCurrentIndex(max(0, method))
                    self.matrix_index.setValue(entry.parameters.get("index", 1))
                    precision = entry.parameters.get("precision")
                    self.matrix_decimal.setChecked(precision is not None)
                    if isinstance(precision, int):
                        self.matrix_precision.setValue(precision)
                    grids = (("A", self.matrix_editor.a), ("B", self.matrix_editor.b))
                    for name, grid in grids:
                        if isinstance(entry.parameters.get(name), str):
                            grid.load(entry.parameters[name])
                if entry.module_id == "multivariable":
                    op_val = entry.parameters.get("operation", "partial")
                    idx = self.mv_op_combo.findData(op_val)
                    if idx >= 0:
                        self.mv_op_combo.setCurrentIndex(idx)
                    vars_list = entry.parameters.get("variables")
                    if isinstance(vars_list, list) and vars_list:
                        self.mv_vars_edit.setText(", ".join(str(v) for v in vars_list))
                    pt = entry.parameters.get("point")
                    if isinstance(pt, dict) and pt:
                        self.mv_point_edit.setText(
                            ", ".join(str(v) for v in pt.values())
                        )
                    direction = entry.parameters.get("direction")
                    if isinstance(direction, list) and direction:
                        self.mv_dir_edit.setText(", ".join(str(v) for v in direction))
            self._on_solve()

    def _clear_results(self) -> None:
        while self.result_layout.count() > 1:
            item = self.result_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        if self.graph_view is not None:
            self.graph_layout.removeWidget(self.graph_view)
            self.graph_view.deleteLater()
            self.graph_view = None
        self._graph_data = []
        self._response = None
        self.matrix_editor.set_results(None)
        self.interpretation_math.hide()
        self.response_card.hide()
        self.empty_state.show()
        self.tabs.setCurrentIndex(0)

    def _on_text_changed(self) -> None:
        self._input_valid = False
        self.btn_solve.setEnabled(False)
        self.interpretation_math.hide()
        self.interpretation_label.setText("Revisando la entrada…")
        self.status_label.setText("Revisando la entrada…")
        if self._response:
            self.result_title.setText("Resultado anterior")
        self.parse_timer.start()

    def _detect_variables(self) -> None:
        text = self.input_editor.toPlainText().strip()
        self._input_valid = False
        self.input_editor.setExtraSelections([])
        self.input_editor.setProperty("invalid", False)
        self.error_preview_label.hide()
        if not text:
            self.interpretation_label.setText("—")
            self.interpretation_math.hide()
            self.status_label.setText("Escribe una expresión válida para resolver.")
        else:
            try:
                structured = self.current_module_id in STRUCTURED_MODULES
                if self.current_module_id == "matrices":
                    ast = None
                    normalized = parse_matrix_input(text).source
                else:
                    ast = self.parser.parse(text, structured=structured)
                    normalized = self.parser.normalizer.normalize(text)
                self._input_valid = True
                self.interpretation_label.setText(normalized)
                self.status_label.setText("Entrada válida")
                if ast is not None and not structured:
                    try:
                        expr = self.adapter.ast_to_sympy(ast)
                        latex_str = sp.latex(expr)
                        self.interpretation_math.render_math(
                            latex_str, display_mode=False
                        )
                        self.interpretation_math.show()
                    except Exception:
                        self.interpretation_math.hide()
                else:
                    self.interpretation_math.hide()
                variables = (
                    [] if structured or ast is None
                    else sorted(self.parser.extract_variables(ast))
                )
                if variables:
                    current = self.var_combo.currentText()
                    self.var_combo.clear()
                    self.var_combo.addItems(variables)
                    if current in variables:
                        self.var_combo.setCurrentText(current)
            except (StructuredMathError, ValueError) as error:
                self.interpretation_label.setText("Revisa la expresión")
                self.interpretation_math.hide()
                self.status_label.setText("Corrige la entrada para resolver.")
                if isinstance(error, StructuredMathError):
                    message = (
                        f"{error.message} en columna {error.column}. {error.suggestion}"
                    )
                    self._highlight_error(error)
                else:
                    message = str(error)
                self.error_preview_label.setText(f"Error de entrada: {message}")
                self.error_preview_label.show()
                self.input_editor.setProperty("invalid", True)
        self.input_editor.style().unpolish(self.input_editor)
        self.input_editor.style().polish(self.input_editor)
        self.btn_solve.setEnabled(
            self._input_valid and self._state == ProcessState.IDLE
        )

    def _highlight_error(self, error: StructuredMathError) -> None:
        selection = QTextEdit.ExtraSelection()
        cursor = self.input_editor.textCursor()
        lines = self.input_editor.toPlainText().splitlines(keepends=True)
        offset = sum(len(line) for line in lines[: max(0, error.line - 1)])
        start = offset + max(0, error.column - 1)
        cursor.setPosition(
            min(start, self.input_editor.document().characterCount() - 1)
        )
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            max(1, error.end_column - error.column),
        )
        selection.cursor = cursor
        selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        selection.format.setUnderlineColor(theme.DANGER)
        self.input_editor.setExtraSelections([selection])

    def _on_controller_state_changed(self, state: ProcessState) -> None:
        self._state = state
        idle = state == ProcessState.IDLE
        running = state == ProcessState.RUNNING
        self.btn_solve.setEnabled(idle and self._input_valid)
        self.btn_cancel.setVisible(not idle)
        self.btn_cancel.setEnabled(running)
        self.btn_cancel.setText("Cancelar" if running else "Deteniendo…")
        self._layout_input_actions()
        self.input_editor.setReadOnly(not idle)
        for control in [
            self.btn_new,
            self.btn_derivadas,
            self.btn_integrales,
            self.btn_multivariable,
            self.btn_ecuaciones,
            *self.structured_nav.values(),
            self.btn_graficadora,
            self.btn_historial,
            self.var_combo,
            self.order_spin,
            self.mv_widget,
            self.structured_controls,
            self.matrix_controls,
            self.btn_toggle_keyboard,
            self.keyboard_widget,
        ]:
            control.setEnabled(idle)
        if hasattr(self, "matrix_editor"):
            self.matrix_editor.set_solving(not idle)
        if running:
            self.status_label.setText("Calculando · Puedes cancelar el cálculo.")
            if self._response:
                self.result_title.setText("Resultado anterior")
        elif state == ProcessState.STOPPING:
            self.status_label.setText("Deteniendo el cálculo · Espera un momento.")
        elif not self._response:
            self.status_label.setText(
                "Entrada válida"
                if self._input_valid
                else "Escribe una expresión válida para resolver."
            )

    def _on_cancel(self) -> None:
        self.worker_controller.cancel()

    def _build_multivariable_params(self) -> dict[str, Any]:
        op = str(self.mv_op_combo.currentData() or "partial")
        raw_vars = [
            v.strip()
            for v in self.mv_vars_edit.text().split(",")
            if v.strip().isidentifier()
        ]
        variables: list[str] = []
        for v in raw_vars:
            if v not in variables:
                variables.append(v)
        for fallback in ("x", "y", "z"):
            if len(variables) >= 2:
                break
            if fallback not in variables:
                variables.append(fallback)
        variables = variables[:3]

        point_vals: list[float] = []
        for token in self.mv_point_edit.text().split(","):
            tok = token.strip()
            if tok:
                try:
                    point_vals.append(float(tok))
                except ValueError:
                    point_vals.append(1.0)
        point_dict = {
            var: (point_vals[idx] if idx < len(point_vals) else 1.0)
            for idx, var in enumerate(variables)
        }

        dir_vals: list[float] = []
        for token in self.mv_dir_edit.text().split(","):
            tok = token.strip()
            if tok:
                try:
                    dir_vals.append(float(tok))
                except ValueError:
                    dir_vals.append(0.0)
        direction_list = [
            dir_vals[idx] if idx < len(dir_vals) else (1.0 if idx == 0 else 0.0)
            for idx in range(len(variables))
        ]
        if all(val == 0.0 for val in direction_list):
            direction_list[0] = 1.0

        return {
            "operation": op,
            "variable": self.var_combo.currentText() or "x",
            "order": self.order_spin.value(),
            "variables": variables,
            "point": point_dict,
            "direction": direction_list,
            "include_graph": True,
        }

    def _on_solve(self) -> None:
        if self._state != ProcessState.IDLE:
            return
        self.parse_timer.stop()
        self._detect_variables()
        if not self._input_valid:
            return
        text = self.input_editor.toPlainText().strip()
        if self.current_module_id == "multivariable":
            params = self._build_multivariable_params()
        elif self.current_module_id in STRUCTURED_MODULES:
            params = {"operation": self.structured_op_combo.currentData()}
            if self.current_module_id == "matrices":
                method = self.matrix_method.currentData()
                if params["operation"] == "determinant" and method != "auto":
                    params.update(method=method, index=self.matrix_index.value())
                if params["operation"] == "expression":
                    params.update(
                        A=self.matrix_editor.a.text(), B=self.matrix_editor.b.text()
                    )
                if self.matrix_decimal.isChecked():
                    params["precision"] = self.matrix_precision.value()
        else:
            params = {
                "variable": self.var_combo.currentText() or "x",
                "include_graph": True,
                "order": self.order_spin.value()
                if self.current_module_id == "derivatives"
                else 1,
            }
        self._active_request = (text, self.current_module_id, dict(params))
        if not self.worker_controller.start(text, self.current_module_id, params):
            self.status_label.setText("Hay un cálculo previo en curso o limpiándose.")

    def _on_solve_error(self, error_msg: str) -> None:
        # El controlador puede emitir diagnóstico técnico: no exponerlo en la vista.
        self.status_label.setText(
            "No se pudo realizar el cálculo. Intenta resolver de nuevo."
        )

    def _on_solve_finished(self, response: SolutionResponse) -> None:
        self._clear_results()
        self._response = response
        self.empty_state.hide()
        self.response_card.show()
        self.notices.hide()
        self.summary.hide()
        self.tabs.hide()
        text, module_id, parameters = self._active_request or (
            response.normalized_input or "",
            self.current_module_id,
            {},
        )
        if response.normalized_input:
            self.interpretation_label.setText(response.normalized_input)
        result = response.calculation.primary_result if response.calculation else None
        if result and response.status.value in (
            "success",
            "success_with_warnings",
            "partial",
            "unevaluated",
        ):
            self.summary.show()
            self.btn_open_in_graph.setVisible(module_id not in STRUCTURED_MODULES)
            if module_id == "matrices":
                self.matrix_editor.set_results(response.calculation)
            self.tabs.show()
            self.result_title.setText(
                "Resultado no evaluado"
                if response.status.value == "unevaluated"
                else "Resultado"
            )
            self.result_math.setAccessibleDescription(result.value.canonical_text)
            self.result_math.render_math(result.value.latex, display_mode=True)
            evaluated = response.status.value != "unevaluated"
            self.verification_label.setText(
                (response.verification or "Verificación no disponible")
                if evaluated
                else "Operación conservada sin evaluar"
            )
            self.verification_label.setProperty(
                "role",
                "success"
                if evaluated
                and response.verification == "Verificado matemáticamente con éxito."
                else "muted",
            )
            self.verification_label.style().unpolish(self.verification_label)
            self.verification_label.style().polish(self.verification_label)
            self.check_label.setText(
                response.verification or "Verificación no disponible"
            )
            self.status_label.setText("Resultado disponible")
            notices = [f"Advertencia: {warning}" for warning in response.warnings]
            if (
                response.procedure
                and response.procedure.coverage != StepCoverage.COMPLETE
            ):
                notices.insert(
                    0,
                    (
                        "Procedimiento parcial: la explicación de esta parte "
                        "todavía no está disponible."
                    )
                    if response.procedure.coverage == StepCoverage.PARTIAL
                    else "Procedimiento no disponible para esta resolución.",
                )
            if notices:
                self.notices.setText("\n".join(notices))
                self.notices.show()
            if response.procedure and response.procedure.steps:
                self._render_steps(response.procedure.steps, 0)
            else:
                self.result_layout.insertWidget(
                    0, _label("No hay pasos disponibles.", "muted")
                )
            self._graph_data = response.graph_data
            self.tabs.setTabVisible(1, bool(self._graph_data))
            self.tabs.setTabVisible(2, evaluated and bool(response.verification))
            entry = HistoryEntry(
                id=response.response_id,
                original_input=text,
                module_id=module_id,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                response_summary=result.value.canonical_text,
                parameters=parameters,
            )
            try:
                self.history_repo.save(entry)
            except Exception:
                self.notices.setText(
                    "\n".join(
                        notices
                        + ["Advertencia: no se pudo guardar en el historial local."]
                    )
                )
                self.notices.show()
        else:
            message = response.error or {
                "cancelled": "Cálculo cancelado. Puedes volver a resolver.",
                "timeout": (
                    "Se agotó el tiempo de cálculo. Prueba una expresión más sencilla."
                ),
                "unsupported": "Operación no disponible para esta expresión.",
                "failed": "No se pudo realizar el cálculo. Intenta resolver de nuevo.",
            }.get(response.status.value, "No se obtuvo un resultado completo.")
            if response.status.value == "failed":
                message = "No se pudo realizar el cálculo. Intenta resolver de nuevo."
            if response.structured_error:
                error = response.structured_error
                message = (
                    f"{error.message} en columna {error.column}. {error.suggestion}"
                )
                self._highlight_error(error)
            self.notices.setText(message)
            self.notices.show()
            self.status_label.setText(message)
        # La respuesta empieza en su resumen, nunca dentro de la pestaña de pasos.
        QTimer.singleShot(
            0,
            lambda: self.work_scroll.ensureWidgetVisible(
                self.summary if result else self.notices, 0, 12
            ),
        )

    def _render_steps(self, steps: list[EducationalStep], indent: int) -> None:
        for number, step in enumerate(steps, 1):
            row = QFrame()
            row.setProperty("role", "step")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4 + min(indent, 3) * 16, 12, 4, 12)
            badge = _label(str(number), "step-number")
            badge.setFixedSize(32, 32)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            contents = QVBoxLayout()
            contents.setSpacing(4)
            contents.addWidget(_label(step.rule_name, "section", True))
            formula = MathView()
            formula.setMinimumHeight(80)
            formula.setAccessibleName(f"Transformación del paso {number}")
            formula.setAccessibleDescription(step.explanation)
            formula.render_math(
                f"{step.before_latex} \\rightarrow {step.after_latex}",
                False,
                explanation=step.explanation,
            )
            contents.addWidget(formula)
            row_layout.addLayout(contents, 1)
            self.result_layout.insertWidget(self.result_layout.count() - 1, row)
            if step.sub_steps:
                count = len(step.sub_steps)
                disclosure = _button(
                    f"Mostrar pasos intermedios ({count}) ▾",
                    lambda: None,
                    "Expandir subpasos",
                )
                disclosure.setCheckable(True)
                disclosure.setProperty("role", "step-disclosure")
                group = QFrame()
                group.setProperty("role", "sub-step-group")
                group_layout = QVBoxLayout(group)
                group_layout.setContentsMargins(16, 0, 0, 0)
                # Reutiliza el mismo renderizador de pasos, conservando toda la traza.
                parent_layout = self.result_layout
                self.result_layout = group_layout
                group_layout.addStretch()
                self._render_steps(step.sub_steps, indent + 1)
                self.result_layout = parent_layout
                group.hide()

                def _toggle(
                    checked: bool,
                    button: QPushButton = disclosure,
                    panel: QFrame = group,
                    total: int = count,
                ) -> None:
                    button.setText(
                        f"Ocultar pasos intermedios ({total}) ▴"
                        if checked
                        else f"Mostrar pasos intermedios ({total}) ▾"
                    )
                    panel.setVisible(checked)

                disclosure.toggled.connect(_toggle)
                contents.addWidget(disclosure)
                contents.addWidget(group)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and self._graph_data and self.graph_view is None:
            self.graph_view = GraphView()
            self.graph_view.setAccessibleName("Gráfica interactiva de la resolución")
            self.graph_layout.addWidget(self.graph_view)
            self.graph_view.render_graph(self._graph_data)

    def _copy_result(self, latex: bool) -> None:
        response = self._response
        if response and response.calculation and response.calculation.primary_result:
            value = response.calculation.primary_result.value
            try:
                QApplication.clipboard().setText(
                    value.latex if latex else value.canonical_text
                )
                self.status_label.setText(
                    "LaTeX copiado" if latex else "Resultado copiado"
                )
            except Exception:
                self.status_label.setText("No se pudo copiar al portapapeles.")

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.worker_controller.shutdown()
        except RuntimeError:
            self.status_label.setText(
                "El cálculo sigue activo. Intenta cerrar nuevamente."
            )
            event.ignore()
            return
        self.parse_timer.stop()
        self.history_repo.close()
        super().closeEvent(event)
