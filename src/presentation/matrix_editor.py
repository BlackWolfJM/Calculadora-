"""Cuadrículas A y B para crear entradas matriciales sin escribir delimitadores."""

import ast
import re

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.errors import StructuredMathError
from src.domain.responses import CalculationBlock
from src.infrastructure.parsing.matrix_parser import MAX_MATRIX_SIZE, parse_matrix_input

Cells = tuple[tuple[str, ...], ...]


def read_matrix_cells(source: str) -> Cells:
    text = source.strip()
    if text.startswith(("[", "{")):
        parsed = parse_matrix_input(text)
        rows = parsed.tree
        if not isinstance(rows, (ast.List, ast.Tuple)):
            raise ValueError("Pega una matriz con una lista por fila.")
        result = []
        for row in rows.elts:
            if not isinstance(row, (ast.List, ast.Tuple)):
                raise ValueError("Pega una matriz con una lista por fila.")
            result.append(
                tuple(ast.get_source_segment(parsed.source, cell) for cell in row.elts)
            )
        cells = tuple(result)
    else:
        lines = [
            line.rstrip("\r") for line in re.split(r"\n|;", source) if line.strip()
        ]
        cells = tuple(
            tuple(
                item.strip()
                for item in (
                    line.split("\t")
                    if "\t" in line
                    else line.split(",")
                    if "," in line
                    else line.split()
                )
            )
            for line in lines
        )
    if not cells or not 1 <= len(cells[0]) <= MAX_MATRIX_SIZE:
        raise ValueError(f"Pega una matriz de 1 a {MAX_MATRIX_SIZE} columnas.")
    if len(cells) > MAX_MATRIX_SIZE or any(len(row) != len(cells[0]) for row in cells):
        raise ValueError(
            "Las filas deben tener la misma longitud y caber en la cuadrícula."
        )
    return cells


class GridTable(QTableWidget):
    paste = Signal(str)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste.emit(QApplication.clipboard().text())
            return
        if event.matches(QKeySequence.StandardKey.Copy) and self.selectedRanges():
            selected = self.selectedRanges()[0]
            text = "\n".join(
                "\t".join(
                    self.item(row, col).text()
                    for col in range(selected.leftColumn(), selected.rightColumn() + 1)
                )
                for row in range(selected.topRow(), selected.bottomRow() + 1)
            )
            QApplication.clipboard().setText(text)
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.selectedItems():
                item.setText("")
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasText():
            self.paste.emit(event.mimeData().text())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class GridChange(QUndoCommand):
    def __init__(self, grid, before: Cells, after: Cells):
        super().__init__()
        self.grid = grid
        self.before = before
        self.after = after

    def undo(self):
        self.grid.show_cells(self.before)

    def redo(self):
        self.grid.show_cells(self.after)


class MatrixGrid(QWidget):
    feedback = Signal(str)

    def __init__(self, name: str, cells: Cells):
        super().__init__()
        self.cells = cells
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(40)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.rows = QSpinBox()
        self.columns = QSpinBox()
        for label, spin in (("Filas", self.rows), ("Columnas", self.columns)):
            spin.setRange(1, MAX_MATRIX_SIZE)
            spin.setAccessibleName(f"{label} de matriz {name}")
            spin.valueChanged.connect(self.resize_grid)
            controls.addWidget(QLabel(label))
            controls.addWidget(spin)
        controls.addStretch()
        layout.addLayout(controls)
        actions = QHBoxLayout()
        for title, action in (
            ("Pegar", lambda: self.load(QApplication.clipboard().text())),
            ("Copiar", lambda: QApplication.clipboard().setText(self.text())),
            ("Limpiar", self.clear),
        ):
            button = QPushButton(title)
            button.clicked.connect(action)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.table = GridTable()
        self.table.setAccessibleName(f"Cuadrícula de matriz {name}")
        self.table.setAcceptDrops(True)
        self.table.setMaximumHeight(170)
        self.table.setMinimumHeight(106)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.itemChanged.connect(self.edit_cell)
        self.table.paste.connect(self.load)
        layout.addWidget(self.table)
        history = QHBoxLayout()
        for title, key, enabled, action in (
            (
                "Deshacer",
                QKeySequence.StandardKey.Undo,
                self.undo_stack.canUndoChanged,
                self.undo_stack.undo,
            ),
            (
                "Rehacer",
                QKeySequence.StandardKey.Redo,
                self.undo_stack.canRedoChanged,
                self.undo_stack.redo,
            ),
        ):
            button = QPushButton(title)
            button.setEnabled(False)
            enabled.connect(button.setEnabled)
            button.clicked.connect(action)
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            history.addWidget(button)
        history.addStretch()
        layout.addLayout(history)
        self.show_cells(cells)

    def text(self) -> str:
        return (
            "["
            + ", ".join(
                "[" + ", ".join(entry.strip() or "0" for entry in row) + "]"
                for row in self.cells
            )
            + "]"
        )

    def show_cells(self, cells: Cells) -> None:
        self.cells = cells
        controls = (self.table, self.rows, self.columns)
        for control in controls:
            control.blockSignals(True)
        self.rows.setValue(len(cells))
        self.columns.setValue(len(cells[0]))
        self.table.setRowCount(len(cells))
        self.table.setColumnCount(len(cells[0]))
        for row, values in enumerate(cells):
            for column, cell in enumerate(values):
                item = self.table.item(row, column)
                if item is None:
                    self.table.setItem(row, column, QTableWidgetItem(cell))
                else:
                    item.setText(cell)
        for control in controls:
            control.blockSignals(False)

    def change(self, cells: Cells) -> None:
        if self.cells != cells:
            self.undo_stack.push(GridChange(self, self.cells, cells))

    def edit_cell(self, item: QTableWidgetItem) -> None:
        row, column = item.row(), item.column()
        rows = [list(values) for values in self.cells]
        rows[row][column] = item.text()
        self.change(tuple(tuple(values) for values in rows))

    def resize_grid(self) -> None:
        self.change(
            tuple(
                tuple(
                    self.cells[row][col]
                    if row < len(self.cells) and col < len(self.cells[0])
                    else ""
                    for col in range(self.columns.value())
                )
                for row in range(self.rows.value())
            )
        )

    def clear(self) -> None:
        self.change(tuple(tuple("" for _ in row) for row in self.cells))

    def load(self, source: str) -> None:
        try:
            self.change(read_matrix_cells(source))
        except (ValueError, StructuredMathError) as exc:
            self.feedback.emit(
                exc.message if isinstance(exc, StructuredMathError) else str(exc)
            )


class DraggableResult(QPushButton):
    def __init__(self, text: str, selector: QComboBox):
        super().__init__(text)
        self.selector = selector
        self.origin = None

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        data = self.selector.currentData()
        if (
            data
            and self.origin is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self.origin).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            mime = QMimeData()
            mime.setText(data)
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction)
            self.origin = None
        super().mouseMoveEvent(event)


class AdaptiveOperands(QWidget):
    """Presenta las mismas cuadrículas en pestañas o en dos columnas."""

    def __init__(self, a: MatrixGrid, b: MatrixGrid):
        super().__init__()
        self.setAccessibleName("Operandos matriciales")
        self._grids = (a, b)
        self._wide = False
        self._tabs = QTabBar()
        self._tabs.setAccessibleName("Matriz activa")
        self._tabs.setExpanding(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)
        self._columns = QHBoxLayout()
        self._columns.setSpacing(12)
        self._selectors = QButtonGroup(self)
        self._panels: list[QWidget] = []
        for index, (name, grid) in enumerate(
            zip(("Matriz A", "Matriz B"), self._grids)
        ):
            self._tabs.addTab(name)
            panel = QWidget()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(0, 0, 0, 0)
            selector = QRadioButton(name)
            selector.setAccessibleName(f"{name} como operando activo")
            self._selectors.addButton(selector, index)
            panel_layout.addWidget(selector)
            panel_layout.addWidget(grid)
            self._columns.addWidget(panel, 1)
            self._panels.append(panel)
        layout.addLayout(self._columns)
        self._tabs.currentChanged.connect(self._sync_operands)
        self._selectors.idClicked.connect(self._tabs.setCurrentIndex)
        QApplication.instance().focusChanged.connect(self._focus_changed)
        self._sync_operands(0)

    def _sync_operands(self, active: int) -> None:
        self._tabs.setVisible(not self._wide)
        for index, panel in enumerate(self._panels):
            selector = self._selectors.button(index)
            selector.setVisible(self._wide)
            selector.setChecked(index == active)
            panel.setVisible(self._wide or index == active)

    def _focus_changed(self, previous, current) -> None:
        if self._wide and current is not None:
            for index, panel in enumerate(self._panels):
                if panel.isAncestorOf(current):
                    self._tabs.setCurrentIndex(index)
                    break

    def currentWidget(self) -> MatrixGrid:
        return self._grids[self._tabs.currentIndex()]

    def setCurrentWidget(self, grid: MatrixGrid) -> None:
        if grid in self._grids:
            self._tabs.setCurrentIndex(self._grids.index(grid))

    def minimumSizeHint(self) -> QSize:
        compact_width = max(
            self._tabs.minimumSizeHint().width(),
            *(grid.minimumSizeHint().width() for grid in self._grids),
        )
        return QSize(compact_width, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        required = sum(grid.minimumSizeHint().width() for grid in self._grids)
        wide = event.size().width() >= required + self._columns.spacing()
        if self._wide != wide:
            self._wide = wide
            self._sync_operands(self._tabs.currentIndex())


class MatrixEditor(QWidget):
    use_grids = Signal()
    operation_requested = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.a = MatrixGrid("A", (("1", "2"), ("3", "4")))
        self.b = MatrixGrid("B", (("5", "6"), ("7", "8")))
        self._action_buttons: list[QPushButton] = []
        actions = QGridLayout()
        for index, (operation, label, name) in enumerate(
            (
                ("add", "A + B", "Sumar A y B"),
                ("subtract", "A − B", "Restar B de A"),
                ("product", "A × B", "Multiplicar A por B"),
                ("transpose", "Transponer", "Transponer la matriz activa"),
                ("determinant", "Determinante", "Determinante de la matriz activa"),
                (
                    "gauss",
                    "Resolver AX = B",
                    (
                        "Resolver el sistema lineal con coeficientes en A "
                        "y términos independientes en B"
                    ),
                ),
            )
        ):
            button = QPushButton(label)
            button.setObjectName(f"matrix-quick-{operation}")
            button.setAccessibleName(name)
            button.setToolTip(name)
            button.clicked.connect(
                lambda checked=False, op=operation: self.operation_requested.emit(op)
            )
            row, column = divmod(index, 3)
            actions.addWidget(button, row, column)
            self._action_buttons.append(button)
        layout.addLayout(actions)
        self.tabs = AdaptiveOperands(self.a, self.b)
        layout.addWidget(self.tabs)
        transfer = QHBoxLayout()
        for title, obj_id, action in (
            ("A → B", "matrix-transfer-a-to-b", lambda: self.copy_grid(self.a, self.b)),
            ("B → A", "matrix-transfer-b-to-a", lambda: self.copy_grid(self.b, self.a)),
            ("Usar A/B", "matrix-use-grids", self.use_grids.emit),
        ):
            button = QPushButton(title)
            button.setObjectName(obj_id)
            button.setAccessibleName(f"Transferencia {title}")
            button.clicked.connect(action)
            transfer.addWidget(button)
        transfer.addStretch()
        layout.addLayout(transfer)
        result_row = QGridLayout()
        self.result_selector = QComboBox()
        self.result_selector.setAccessibleName("Resultado matricial que se reutilizará")
        result_row.addWidget(self.result_selector, 0, 0, 1, 2)
        for column, (name, grid) in enumerate((("A", self.a), ("B", self.b))):
            button = DraggableResult(f"Copiar a {name}", self.result_selector)
            button.setObjectName(f"matrix-copy-to-{name.lower()}")
            button.setAccessibleName(f"Copiar resultado a matriz {name}")
            button.setToolTip(f"Copiar el resultado seleccionado a la matriz {name}")
            button.clicked.connect(
                lambda checked=False, target=grid: self.copy_result(target)
            )
            result_row.addWidget(button, 1, column)
        self.results = QWidget()
        self.results.setLayout(result_row)
        self.results.hide()
        layout.addWidget(self.results)
        self.feedback = QLabel()
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.feedback.setWordWrap(True)
        self.feedback.setProperty("role", "muted")
        layout.addWidget(self.feedback)
        self.a.feedback.connect(self.feedback.setText)
        self.b.feedback.connect(self.feedback.setText)

    def copy_grid(self, source: MatrixGrid, target: MatrixGrid) -> None:
        target.change(source.cells)
        self.tabs.setCurrentWidget(target)

    def copy_result(self, target: MatrixGrid) -> None:
        data = self.result_selector.currentData()
        if data:
            target.load(data)
            self.tabs.setCurrentWidget(target)

    def load_example(self, source: str, kind: str) -> str | None:
        self.tabs.setCurrentWidget(self.a)
        if kind == "expression":
            self.a.load("[[1, 2], [3, 4]]")
            self.b.load("[[5, 6], [7, 8]]")
        elif kind in {"binary", "argument"}:
            parsed = parse_matrix_input(source)
            first, second = parsed.tree.elts
            self.a.load(ast.get_source_segment(parsed.source, first))
            if kind == "binary":
                self.b.load(ast.get_source_segment(parsed.source, second))
            else:
                return ast.get_source_segment(parsed.source, second)
        else:
            self.a.load(source)
        return None

    def set_results(self, calculation: CalculationBlock | None) -> None:
        self.result_selector.clear()
        if calculation:
            items = calculation.related_results or [calculation.primary_result]
            for item in items:
                if item and item.value.canonical_text.startswith("[["):
                    self.result_selector.addItem(item.label, item.value.canonical_text)
        self.results.setVisible(self.result_selector.count() > 0)

    def set_solving(self, solving: bool) -> None:
        """Habilita o deshabilita los botones de acción durante el cálculo."""
        for button in self._action_buttons:
            button.setEnabled(not solving)
