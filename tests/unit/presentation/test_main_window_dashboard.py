"""Regresiones del dashboard Qt: estados, respuesta visible y datos originales."""

from dataclasses import replace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from src.domain.responses import (
    CalculationBlock,
    MathPayload,
    ResolutionStatus,
    ResultItem,
    SolutionResponse,
)
from src.domain.steps import EducationalStep, StepCoverage, StepOutcome, StepStatus
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sqlite_history import SQLiteHistoryRepository
from src.presentation import theme
from src.presentation.calculation_process_controller import ProcessState
from src.presentation.main_window import MainWindow


class FormulaStub(QWidget):
    def render_math(self, latex_content, display_mode=True, explanation=""):
        self.latex = latex_content


@pytest.fixture
def window(qtbot, monkeypatch):
    # Las pruebas de comportamiento no necesitan Chromium; la GUI real se prueba
    # además mediante test_ui y el recorrido documentado de qa_gui.py.
    monkeypatch.setattr("src.presentation.main_window.MathView", FormulaStub)
    history = SQLiteHistoryRepository(":memory:")
    result = MainWindow(None, history, MathParser())
    qtbot.addWidget(result)
    result.show()
    yield result
    result.close()


def answer(coverage=StepCoverage.COMPLETE):
    return SolutionResponse(
        response_id="dashboard-test",
        status=ResolutionStatus.SUCCESS,
        normalized_input="x^2*sin(x)",
        calculation=CalculationBlock(
            "success",
            ResultItem(
                MathPayload("x**2*cos(x) + 2*x*sin(x)", r"x^2\cos(x)+2x\sin(x)"),
                "Resultado",
            ),
        ),
        verification="Verificado matemáticamente con éxito.",
        procedure=StepOutcome(
            StepStatus.SUCCESS,
            coverage,
            [
                EducationalStep(
                    "product",
                    "Regla del producto",
                    "Derivamos ambos factores.",
                    r"x^2\sin(x)",
                    r"x^2\cos(x)+2x\sin(x)",
                )
            ],
        ),
        graph_data=[{"x": [0, 1], "y": [0, 0.84], "type": "scatter"}],
    )


def valid_input(window):
    window.input_editor.setPlainText("x^2*sin(x)")
    window.parse_timer.stop()
    window._detect_variables()


def test_matrix_example_runs_in_worker_and_persists_operation(window, qtbot):
    window.structured_nav["matrices"].click()
    window.structured_op_combo.setCurrentIndex(
        window.structured_op_combo.findData("inverse")
    )
    window.btn_example.click()
    assert window.input_editor.toPlainText() == "[[2, 1], [1, 1]]"
    assert window.var_combo.isHidden()

    with qtbot.waitSignal(window.worker_controller.idle, timeout=15000):
        window.btn_solve.click()

    assert window.summary.isVisible()
    assert window.btn_open_in_graph.isHidden()
    assert window.result_math.accessibleDescription() == "[[1, -1], [-1, 2]]"
    entry = window.history_repo.get_all(limit=1)[0]
    assert entry.module_id == "matrices"
    assert entry.parameters == {"operation": "inverse"}


def test_matrix_grids_build_expression_and_reuse_worker_factors(window, qtbot):
    window.resize(820, 600)
    window.structured_nav["matrices"].click()
    window.structured_op_combo.setCurrentIndex(window.structured_op_combo.findData("lu"))
    window.btn_matrix_editor.click()
    qtbot.wait(20)
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    editor = window.matrix_editor
    editor.a.load("0\t2\n3\t4")
    editor.a.undo_stack.undo()
    assert editor.a.text() == "[[1, 2], [3, 4]]"
    editor.a.undo_stack.redo()
    editor.use_grids.emit()
    assert window.input_editor.toPlainText() == "[[0, 2], [3, 4]]"
    with qtbot.waitSignal(window.worker_controller.idle, timeout=15000):
        window.btn_solve.click()
    assert window.summary.isVisible()
    assert editor.result_selector.count() == 3
    editor.result_selector.setCurrentIndex(editor.result_selector.findText("U"))
    editor.copy_result(editor.b)
    assert editor.b.text() == "[[3, 4], [0, 2]]"


def test_matrix_grids_preserve_operands_when_switching_layout(window, qtbot):
    window.resize(820, 600)
    window.structured_nav["matrices"].click()
    window.btn_matrix_editor.click()
    editor = window.matrix_editor
    a, b = editor.a, editor.b
    b.load("9\t1/3\n2\t7")
    editor.tabs.setCurrentWidget(b)
    qtbot.waitUntil(lambda: b.isVisible() and not a.isVisible())

    window.resize(1180, 760)
    qtbot.waitUntil(lambda: a.isVisible() and b.isVisible())
    assert editor.tabs.currentWidget() is b
    assert a.mapTo(editor, a.rect().topLeft()).x() < (
        b.mapTo(editor, b.rect().topLeft()).x()
    )
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    editor.use_grids.emit()
    assert window.input_editor.toPlainText() == "[[9, 1/3], [2, 7]]"

    window.resize(820, 600)
    qtbot.waitUntil(lambda: b.isVisible() and not a.isVisible())
    assert editor.a is a and editor.b is b
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    assert b.text() == "[[9, 1/3], [2, 7]]"
    b.undo_stack.undo()
    assert b.text() == "[[5, 6], [7, 8]]"


def test_matrix_quick_actions_resolve_from_grids_and_save_history(window, qtbot):
    window.resize(820, 600)
    window.structured_nav["matrices"].click()
    window.btn_matrix_editor.click()
    editor = window.matrix_editor
    editor.b.load("5 6\n7 9")
    editor.tabs.setCurrentWidget(editor.b)
    transpose = editor.findChild(QPushButton, "matrix-quick-transpose")
    subtract = editor.findChild(QPushButton, "matrix-quick-subtract")
    gauss = editor.findChild(QPushButton, "matrix-quick-gauss")
    assert transpose is not None and subtract is not None and gauss is not None

    with qtbot.waitSignal(window.worker_controller.idle, timeout=15000):
        transpose.click()
        assert not subtract.isEnabled()
        assert not gauss.isEnabled()
    assert window.result_math.accessibleDescription() == "[[5, 7], [6, 9]]"
    assert editor.tabs.currentWidget() is editor.b

    with qtbot.waitSignal(window.worker_controller.idle, timeout=15000):
        subtract.click()
    assert window.result_math.accessibleDescription() == "[[-4, -4], [-4, -5]]"
    entry = window.history_repo.get_all(limit=1)[0]
    assert entry.parameters == {"operation": "subtract"}

    editor.a.load("1 2\n3 4")
    editor.b.load("5 6\n7 8")
    with qtbot.waitSignal(window.worker_controller.idle, timeout=15000):
        gauss.click()
    assert window.result_math.accessibleDescription() == "[[-3, -4], [4, 5]]"
    entry_gauss = window.history_repo.get_all(limit=1)[0]
    assert entry_gauss.parameters == {"operation": "gauss"}
    assert window.work_scroll.horizontalScrollBar().maximum() == 0


def test_graph_workspace_navigation_preserves_solver(window, monkeypatch):
    monkeypatch.setattr(
        "src.presentation.graphing_workspace.GraphingWorkspace", QWidget
    )
    valid_input(window)

    window.btn_graficadora.click()
    graphing = window.workspace_stack.currentWidget()
    assert graphing is not window.work_scroll
    assert window.btn_graficadora.isChecked()
    assert window.btn_new.isHidden()
    assert not any(shortcut.isEnabled() for shortcut in window._solver_shortcuts)

    window.btn_derivadas.click()
    assert window.workspace_stack.currentWidget() is window.work_scroll
    assert window.input_editor.toPlainText() == "x^2*sin(x)"
    assert window.btn_derivadas.isChecked()
    assert window.btn_solve.isEnabled()
    assert all(shortcut.isEnabled() for shortcut in window._solver_shortcuts)

    window.btn_graficadora.click()
    assert window.workspace_stack.currentWidget() is graphing


def test_main_window_validation_and_recovery(window):
    assert not window.btn_solve.isEnabled()
    assert window.btn_cancel.isHidden()
    valid_input(window)
    assert window.btn_solve.isEnabled()
    assert window.status_label.text() == "Entrada válida"
    window.input_editor.setPlainText("sin(")
    window._detect_variables()
    assert not window.btn_solve.isEnabled()
    assert not window.error_preview_label.isHidden()
    assert window.input_editor.extraSelections()
    valid_input(window)
    assert window.error_preview_label.isHidden()
    assert window.btn_solve.isEnabled()


def test_main_window_running_stopping_and_idle(window):
    valid_input(window)
    cancel = Mock()
    window.worker_controller.cancel = cancel
    window._on_controller_state_changed(ProcessState.RUNNING)
    assert not window.btn_solve.isEnabled()
    assert window.btn_cancel.isVisible()
    assert window.input_editor.toPlainText() == "x^2*sin(x)"
    assert window.input_editor.isReadOnly()
    assert "Calculando" in window.status_label.text()
    window.btn_cancel.click()
    cancel.assert_called_once()
    window._on_controller_state_changed(ProcessState.STOPPING)
    assert not window.btn_cancel.isEnabled()
    assert "Deteniendo" in window.status_label.text()
    window._on_controller_state_changed(ProcessState.IDLE)
    assert window.btn_cancel.isHidden()
    assert window.btn_solve.isEnabled()
    assert not window.input_editor.isReadOnly()


def test_main_window_navigation_identifiers_and_new(window):
    valid_input(window)
    for button, module in [
        (window.btn_integrales, "integrals"),
        (window.btn_ecuaciones, "equations"),
        (window.btn_derivadas, "derivatives"),
    ]:
        button.click()
        assert window.current_module_id == module
        assert button.isChecked()
        assert window.order_spin.isHidden() == (module != "derivatives")
    window.btn_new.click()
    assert not window.input_editor.toPlainText()
    assert not window.btn_solve.isEnabled()


def test_main_window_result_stays_above_tabs_and_graph_is_lazy(window):
    valid_input(window)
    response = answer()
    window._on_solve_finished(response)
    assert window.summary.isVisible()
    assert window.summary.parent() != window.tabs
    assert window.graph_view is None
    assert window._graph_data is response.graph_data
    assert window.result_math.latex == response.calculation.primary_result.value.latex
    window.tabs.setCurrentIndex(2)
    assert window.summary.isVisible()
    assert window.check_label.text() == response.verification
    window.btn_copy.click()
    assert (
        QApplication.clipboard().text()
        == response.calculation.primary_result.value.canonical_text
    )
    window.btn_copy_latex.click()
    assert (
        QApplication.clipboard().text()
        == response.calculation.primary_result.value.latex
    )
    assert window.history_repo.get_all()[0].original_input == "x^2*sin(x)"


def test_main_window_partial_is_explicit_and_warnings_stay_visible(window):
    response = replace(
        answer(StepCoverage.PARTIAL),
        status=ResolutionStatus.PARTIAL,
        warnings=["Dominio restringido"],
    )
    window._on_solve_finished(response)
    assert window.summary.isVisible()
    assert "Procedimiento parcial" in window.notices.text()
    assert "Dominio restringido" in window.notices.text()
    window.tabs.setCurrentIndex(2)
    assert window.notices.isVisible()


def test_main_window_error_retains_input_and_hides_technical_details(window):
    valid_input(window)
    window._on_solve_finished(
        SolutionResponse(
            "error", ResolutionStatus.FAILED, error="Traceback secret path"
        )
    )
    assert "Traceback" not in window.notices.text()
    assert not window.summary.isVisible()
    assert window.input_editor.toPlainText() == "x^2*sin(x)"
    assert window.btn_solve.isEnabled()
    assert not window.history_repo.get_all()


def test_main_window_small_size_accessibility_and_keyboard(window, qtbot):
    window.resize(820, 600)
    valid_input(window)
    window._on_solve_finished(answer())
    qtbot.wait(20)
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    assert window.width() == 820
    for control in [
        window.input_editor,
        window.var_combo,
        window.order_spin,
        window.btn_solve,
        window.btn_cancel,
        window.btn_copy,
        window.btn_copy_latex,
        window.btn_historial,
    ]:
        assert control.accessibleName()
        assert control.height() >= 40
    window.input_editor.setFocus()
    qtbot.keyClick(window.input_editor, Qt.Key.Key_Tab)
    assert window.var_combo.hasFocus()
    assert f"2px solid {theme.FOCUS}" in window.styleSheet()


def test_main_window_untrusted_notices_are_plain_text(window):
    window._on_solve_finished(
        replace(answer(), warnings=['<img src="https://invalid">'])
    )
    assert window.notices.textFormat() == Qt.TextFormat.PlainText
    assert "<img" in window.notices.text()
    assert all(
        label.textFormat() == Qt.TextFormat.PlainText
        for label in window.result_content.findChildren(QLabel)
    )


def test_main_window_math_rendering_keeps_local_resources_and_limits():
    from src.presentation.math_view import MathView

    view = Mock()
    view.property.return_value = 32
    view.accessibleDescription.return_value = "Resultado accesible"
    MathView.render_math(view, r"x^2", explanation='<img src="https://invalid">')
    view.hide.assert_called_once()
    document = view.setHtml.call_args.args[0]
    assert view.setHtml.call_args.args[1] == "math://katex/"
    assert 'src="math://katex/katex.min.js"' in document
    assert "trust: false" in document
    assert "maxSize: 20" in document
    assert "maxExpand: 1000" in document
    assert '<img src="https://invalid">' not in document
    assert "span.textContent = part" in document
    assert "Resultado accesible" in document


def test_main_window_graph_passes_original_coordinates_without_mutation():
    import json

    from src.presentation.graph_view import GraphView

    traces = [{"x": [-10.0, 0, 10.0], "y": [None, 0, -54.4], "type": "scatter"}]
    view = Mock()
    view._loaded = True
    GraphView.render_graph(view, traces)
    script = view.page.return_value.runJavaScript.call_args.args[0]
    decoded = json.loads(
        json.loads(script.removeprefix("renderPlot(").removesuffix(");"))
    )
    assert decoded == traces
    assert view._pending_traces is traces


def test_main_window_unevaluated_never_appears_verified(window):
    window._on_solve_finished(replace(answer(), status=ResolutionStatus.UNEVALUATED))
    assert window.result_title.text() == "Resultado no evaluado"
    assert window.verification_label.text() == "Operación conservada sin evaluar"
    assert window.verification_label.property("role") != "success"
    assert not window.tabs.isTabVisible(2)


def keyboard_keys(window):
    return {
        button.text(): button
        for button in window.keyboard_widget.findChildren(QPushButton)
    }


@pytest.mark.parametrize("width,height", [(1180, 760), (820, 600)])
def test_math_keyboard_toggle_preserves_resolution(window, qtbot, width, height):
    window.resize(width, height)
    valid_input(window)
    window.order_spin.setValue(2)
    response = answer()
    window._on_solve_finished(response)
    toggle = window.btn_toggle_keyboard
    assert window.keyboard_widget.isHidden()
    assert toggle.accessibleName() == "Teclado matemático"
    assert "cerrado" in toggle.accessibleDescription()
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert toggle.isChecked()
    assert "abierto" in toggle.accessibleDescription()
    qtbot.wait(20)
    viewport = window.work_scroll.viewport()
    for control in (window.btn_solve, toggle, *keyboard_keys(window).values()):
        assert control.isVisible() and control.isEnabled()
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().topLeft())
        )
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        )
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert window.keyboard_widget.isHidden()
    assert "cerrado" in toggle.accessibleDescription()
    assert window.input_editor.toPlainText() == "x^2*sin(x)"
    assert window.var_combo.currentText() == "x"
    assert window.order_spin.value() == 2
    assert window._response is response
    assert window.summary.isVisible()


def test_math_keyboard_inserts_and_replaces_at_editor_cursor(window, qtbot):
    window.btn_toggle_keyboard.click()
    keys = keyboard_keys(window)
    assert set(keys) == set("0123456789().x^=*/+-") | {
        "sin()",
        "cos()",
        "tan()",
        "ln()",
        "sqrt()",
        "abs()",
        "pi",
        "e",
        "DEL",
        "AC",
    }
    editor = window.input_editor
    editor.setPlainText("7+15")
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)
    qtbot.mouseClick(keys["x"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "7+x15"
    assert editor.textCursor().position() == 3
    cursor.setPosition(2)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    qtbot.mouseClick(keys["sin()"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "7+sin()"
    assert editor.textCursor().position() == 6
    qtbot.mouseClick(keys["x"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "7+sin(x)"
    qtbot.mouseClick(keys["DEL"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "7+sin()"
    editor.selectAll()
    qtbot.mouseClick(keys["DEL"], Qt.MouseButton.LeftButton)
    assert not editor.toPlainText()
    editor.setPlainText("t^2")
    window._detect_variables()
    assert window.interpretation_math.isVisible()
    assert hasattr(window.interpretation_math, "latex")
    assert "t^{2}" in window.interpretation_math.latex
    qtbot.mouseClick(keys["AC"], Qt.MouseButton.LeftButton)
    assert not editor.toPlainText()
    assert window.interpretation_math.isHidden()
    qtbot.mouseClick(keys["abs()"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "abs()"
    assert editor.textCursor().position() == 4
    qtbot.mouseClick(keys["5"], Qt.MouseButton.LeftButton)
    window._detect_variables()
    assert window.var_combo.currentText() == "t"


def test_math_keyboard_tab_and_space_with_prior_result(window, qtbot):
    valid_input(window)
    window._on_solve_finished(answer())
    toggle = window.btn_toggle_keyboard
    toggle.setFocus()
    qtbot.keyClick(toggle, Qt.Key.Key_Space)
    keys = keyboard_keys(window)
    qtbot.keyClick(toggle, Qt.Key.Key_Tab)
    assert keys["sin()"].hasFocus()
    qtbot.keyClick(keys["sin()"], Qt.Key.Key_Space)
    assert keys["sin()"].hasFocus()
    assert "sin()" in window.input_editor.toPlainText()
    qtbot.keyClick(keys["sin()"], Qt.Key.Key_Tab)
    assert keys["cos()"].hasFocus()


@pytest.mark.parametrize("width", [820, 1000, 1180])
def test_math_keyboard_remains_open_but_locked_until_idle(window, qtbot, width):
    window.resize(width, 600)
    valid_input(window)
    window.btn_toggle_keyboard.click()
    window._on_controller_state_changed(ProcessState.RUNNING)
    qtbot.wait(20)
    assert window.keyboard_widget.isVisible()
    assert not window.btn_toggle_keyboard.isEnabled()
    assert not keyboard_keys(window)["AC"].isEnabled()
    assert window.btn_cancel.isVisible() and window.btn_cancel.isEnabled()
    assert window.work_scroll.horizontalScrollBar().maximum() == 0
    window._on_controller_state_changed(ProcessState.STOPPING)
    assert not window.btn_cancel.isEnabled()
    window._on_controller_state_changed(ProcessState.IDLE)
    assert window.keyboard_widget.isVisible()
    assert keyboard_keys(window)["AC"].isEnabled()
    assert window.btn_solve.isEnabled()
    assert window.input_editor.toPlainText() == "x^2*sin(x)"


def test_ctrl_enter_solves_current_expression_without_debounce(window, qtbot):
    start = Mock(return_value=True)
    window.worker_controller.start = start
    window.activateWindow()
    window.input_editor.setFocus()
    qtbot.waitUntil(window.input_editor.hasFocus)
    qtbot.keyClicks(window.input_editor, "x^2 + 3x")
    qtbot.keyClick(
        window.input_editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: start.call_count == 1)
    assert start.call_args.args[:2] == ("x^2 + 3x", "derivatives")
    assert window.input_editor.toPlainText() == "x^2 + 3x"


def test_step_explanation_delimiters_and_qcolor_background():
    from PySide6.QtGui import QColor

    from src.presentation.math_view import MathView, _normalize_explanation_delimiters

    raw = (
        r"Se aplica la regla del producto (u·v)' = u'·v + u·v' "
        r"con u = x^{2} y v = \sin{\left(x \right)}."
    )
    normalized = _normalize_explanation_delimiters(raw)
    assert r"\(u = x^{2}\)" in normalized
    assert r"\(v = \sin{\left(x \right)}\)" in normalized

    view = Mock()
    view.property.return_value = 32
    view.accessibleDescription.return_value = "Resultado accesible"
    MathView.render_math(view, r"x^2", explanation=raw)
    bg_arg = view.page.return_value.setBackgroundColor.call_args.args[0]
    assert isinstance(bg_arg, QColor)


def test_history_dialog_search_filter_copy_and_keyboard(qtbot):
    import datetime

    from src.domain.history import HistoryEntry
    from src.presentation.history_dialog import HistoryDialog

    repo = SQLiteHistoryRepository(":memory:")
    repo.save(
        HistoryEntry(
            id="h1",
            original_input="x^2 + 3*x",
            module_id="derivatives",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            response_summary="2*x + 3",
            parameters={"variable": "x", "order": 1},
        )
    )
    repo.save(
        HistoryEntry(
            id="h2",
            original_input="sin(x)",
            module_id="integrals",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            response_summary="-cos(x) + C",
            parameters={"variable": "x"},
        )
    )

    dlg = HistoryDialog(repo)
    qtbot.addWidget(dlg)
    dlg.show()

    assert dlg.list_widget.count() == 2
    dlg.search_input.setText("sin")
    assert dlg.list_widget.count() == 1
    dlg.btn_copy.click()
    assert QApplication.clipboard().text() == "-cos(x) + C"

    dlg.search_input.clear()
    dlg.module_filter.setCurrentIndex(dlg.module_filter.findData("derivatives"))
    assert dlg.list_widget.count() == 1

    qtbot.keyClick(dlg, Qt.Key.Key_Return)
    assert dlg.selected_entry is not None
    assert dlg.selected_entry.original_input == "x^2 + 3*x"
    dlg.close()
    repo.close()


def test_send_to_graph_workspace_loads_solver_expression(window, monkeypatch):
    class StubWorkspace(QWidget):
        def __init__(self):
            super().__init__()
            self.loaded = None

        def load_from_solver(self, expr, mod, var):
            self.loaded = (expr, mod, var)

    monkeypatch.setattr(
        "src.presentation.graphing_workspace.GraphingWorkspace", StubWorkspace
    )
    valid_input(window)
    window._on_solve_finished(answer())
    window.btn_open_in_graph.click()

    current = window.workspace_stack.currentWidget()
    assert isinstance(current, StubWorkspace)
    assert current.loaded == ("x^2*sin(x)", "derivatives", "x")


def test_main_window_multivariable_module_navigation_and_parameters(window):
    start = Mock(return_value=True)
    window.worker_controller.start = start

    window.btn_multivariable.click()
    assert window.current_module_id == "multivariable"
    assert window.btn_multivariable.isChecked()
    assert not window.mv_widget.isHidden()

    window.input_editor.setPlainText("x^2*y + y^3")
    window.parse_timer.stop()
    window._detect_variables()
    assert window.btn_solve.isEnabled()

    # Operación por defecto: derivada parcial
    window._on_solve()
    assert start.call_count == 1
    expr, mod, params = start.call_args.args
    assert expr == "x^2*y + y^3"
    assert mod == "multivariable"
    assert params["operation"] == "partial"

    # Cambiar a derivada direccional
    idx = window.mv_op_combo.findData("directional")
    window.mv_op_combo.setCurrentIndex(idx)
    assert not window.mv_vars_edit.isHidden()
    assert not window.mv_point_edit.isHidden()
    assert not window.mv_dir_edit.isHidden()
    window.mv_vars_edit.setText("x, y")
    window.mv_point_edit.setText("1, 2")
    window.mv_dir_edit.setText("3, 4")

    window._on_solve()
    assert start.call_count == 2
    _, _, dir_params = start.call_args.args
    assert dir_params["operation"] == "directional"
    assert dir_params["variables"] == ["x", "y"]
    assert dir_params["point"] == {"x": 1.0, "y": 2.0}
    assert dir_params["direction"] == [3.0, 4.0]


def test_step_substeps_disclosure_counts_and_toggles(window):
    from PySide6.QtWidgets import QFrame

    child = EducationalStep("child", "Paso hijo", "Detalle", "a", "b")
    parent = EducationalStep(
        "parent", "Paso padre", "Detalle", "a", "b", [child, child]
    )
    window._clear_results()
    window._render_steps([parent], 0)

    disclosures = [
        item
        for item in window.result_content.findChildren(QPushButton)
        if item.property("role") == "step-disclosure"
    ]
    groups = [
        item
        for item in window.result_content.findChildren(QFrame)
        if item.property("role") == "sub-step-group"
    ]
    assert len(disclosures) == 1
    assert len(groups) == 1
    disclosure, group = disclosures[0], groups[0]
    assert disclosure.text() == "Mostrar pasos intermedios (2) ▾"
    assert group.isHidden()

    disclosure.click()
    assert disclosure.text() == "Ocultar pasos intermedios (2) ▴"
    assert not group.isHidden()

    disclosure.click()
    assert disclosure.text() == "Mostrar pasos intermedios (2) ▾"
    assert group.isHidden()


def test_math_view_marks_substitution_fragments():
    from src.presentation.math_view import MathView

    view = Mock()
    view.property.return_value = None
    view.accessibleDescription.return_value = ""
    MathView.render_math(
        view,
        r"x",
        explanation=r"Hacemos \(u = x^2\) y \(du = 2x\,dx\).",
    )
    document = view.setHtml.call_args.args[0]

    assert ".subst-u {" in document
    assert ".subst-du {" in document
    assert 'span.className = "math-seg subst-u"' in document
    assert 'span.className = "math-seg subst-du"' in document
    assert "(du|dv)" in document
    assert "(u|v)" in document

