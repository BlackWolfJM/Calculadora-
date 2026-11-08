from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.domain.history import HistoryEntry, HistoryRepository
from src.presentation import theme
from src.presentation.structured_catalog import MODULES as STRUCTURED_MODULES


class HistoryDialog(QDialog):
    def __init__(
        self, history_repo: HistoryRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.history_repo = history_repo
        self.selected_entry: HistoryEntry | None = None
        self._all_entries: list[HistoryEntry] = []

        self.setWindowTitle("Historial de Operaciones")
        self.setMinimumSize(620, 460)
        self.setStyleSheet(theme.QSS)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header = QLabel("Historial")
        header.setObjectName("module-title")
        header_row.addWidget(header)
        header_row.addStretch()
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "muted")
        header_row.addWidget(self.count_label)
        layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("history-search")
        self.search_input.setPlaceholderText(
            "Buscar por expresión o resultado… (Ctrl+F)"
        )
        self.search_input.setAccessibleName("Buscar en el historial")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self.search_input, 2)

        self.module_filter = QComboBox()
        self.module_filter.setAccessibleName("Filtrar por módulo")
        for label, value in (
            ("Todos los módulos", "all"),
            ("Derivadas", "derivatives"),
            ("Integrales", "integrals"),
            ("Ecuaciones", "equations"),
            ("Multivariable", "multivariable"),
        ):
            self.module_filter.addItem(label, value)
        for key, module in STRUCTURED_MODULES.items():
            self.module_filter.addItem(module.title, key)
        self.module_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.module_filter, 1)
        layout.addLayout(filter_row)

        self.list_widget = QListWidget()
        self.list_widget.setAccessibleName("Operaciones guardadas")
        self.list_widget.setWordWrap(True)
        self.list_widget.itemActivated.connect(lambda _: self._on_restore())
        self.list_widget.itemSelectionChanged.connect(self._sync_actions)

        self.empty = QLabel("Las operaciones que resuelvas aparecerán aquí.")
        self.empty.setProperty("role", "empty-state")
        layout.addWidget(self.empty)
        layout.addWidget(self.list_widget, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_clear = QPushButton("Borrar historial")
        self.btn_clear.setObjectName("btn-clear")
        self.btn_clear.setIcon(theme.icon("trash", theme.DANGER))
        self.btn_clear.setAccessibleName("Borrar historial")
        self.btn_clear.setAutoDefault(False)
        self.btn_clear.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()

        self.btn_copy = QPushButton("Copiar resultado")
        self.btn_copy.setIcon(theme.icon("copy"))
        self.btn_copy.setAccessibleName("Copiar resultado seleccionado")
        self.btn_copy.setAutoDefault(False)
        self.btn_copy.clicked.connect(self._on_copy_result)
        btn_layout.addWidget(self.btn_copy)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.setAccessibleName("Cerrar historial")
        self.btn_close.setAutoDefault(False)
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        self.btn_restore = QPushButton("Volver a resolver")
        self.btn_restore.setObjectName("btn-solve")
        self.btn_restore.setIcon(theme.icon("solve", theme.SURFACE))
        self.btn_restore.setAccessibleName("Volver a resolver operación seleccionada")
        self.btn_restore.setAutoDefault(False)
        self.btn_restore.clicked.connect(self._on_restore)
        btn_layout.addWidget(self.btn_restore)

        layout.addLayout(btn_layout)

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self.search_input.setFocus)
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._on_copy_result)

        for first, second in (
            (self.search_input, self.module_filter),
            (self.module_filter, self.list_widget),
            (self.list_widget, self.btn_restore),
            (self.btn_restore, self.btn_copy),
            (self.btn_copy, self.btn_close),
            (self.btn_close, self.btn_clear),
        ):
            QWidget.setTabOrder(first, second)

    def _load_data(self) -> None:
        self.empty.setText("Las operaciones que resuelvas aparecerán aquí.")
        self._all_entries = []
        try:
            self._all_entries = list(self.history_repo.get_all(limit=50))
        except Exception:
            self.empty.setText("No se pudo cargar el historial.")
        self._apply_filters()

    def _apply_filters(self) -> None:
        self.list_widget.clear()
        query = self.search_input.text().strip().lower()
        selected_module = str(self.module_filter.currentData() or "all")
        module_names = {
            "derivatives": "Derivada",
            "integrals": "Integral",
            "equations": "Ecuación",
            "multivariable": "Multivariable",
            **{key: module.title for key, module in STRUCTURED_MODULES.items()},
        }

        filtered: list[HistoryEntry] = []
        for entry in self._all_entries:
            if selected_module != "all" and entry.module_id != selected_module:
                continue
            mod_name = module_names.get(entry.module_id, entry.module_id)
            module = STRUCTURED_MODULES.get(entry.module_id)
            if module and entry.parameters:
                operation = module.operations.get(entry.parameters.get("operation"))
                if operation:
                    mod_name = f"{mod_name} · {operation.name}"
            haystack = (
                f"{mod_name} {entry.original_input} {entry.response_summary}".lower()
            )
            if query and query not in haystack:
                continue
            filtered.append(entry)

            date_str = entry.created_at.strftime("%Y-%m-%d %H:%M")
            display_text = (
                f"{mod_name} · {date_str}\n"
                f"{entry.original_input}  →  {entry.response_summary}"
            )
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)

        if self._all_entries and not filtered:
            self.empty.setText("No hay operaciones que coincidan con el filtro actual.")
        elif not self._all_entries and "No se pudo" not in self.empty.text():
            self.empty.setText("Las operaciones que resuelvas aparecerán aquí.")

        total = len(self._all_entries)
        shown = len(filtered)
        self.count_label.setText(
            f"{shown} de {total} operaciones" if total else "Sin operaciones"
        )

        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self._sync_actions()

    def _sync_actions(self) -> None:
        has_any_saved = len(self._all_entries) > 0
        has_visible = self.list_widget.count() > 0
        has_selected = bool(self.list_widget.selectedItems())
        self.empty.setVisible(not has_visible)
        self.list_widget.setVisible(has_visible)
        self.btn_clear.setEnabled(has_any_saved)
        self.btn_restore.setEnabled(has_selected)
        self.btn_copy.setEnabled(has_selected)

    def _on_copy_result(self) -> None:
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        entry = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, HistoryEntry):
            try:
                QApplication.clipboard().setText(entry.response_summary)
            except Exception:
                pass

    def _on_clear(self) -> None:
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Estás seguro de que deseas borrar todo el historial?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.history_repo.clear()
                self._load_data()
            except Exception:
                QMessageBox.warning(self, "Error", "No se pudo borrar el historial.")

    def _on_restore(self) -> None:
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        entry = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, HistoryEntry):
            self.selected_entry = entry
            self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.list_widget.selectedItems():
                self._on_restore()
                return
        super().keyPressEvent(event)
