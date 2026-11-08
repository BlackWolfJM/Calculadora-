"""Pruebas unitarias para la transferencia de matrices en MatrixEditor (TASK-009).

Verifica que los botones "Copiar a A", "Copiar a B", "A → B" y "B → A"
permitan reutilizar resultados y transferir operandos directamente.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from src.domain.responses import CalculationBlock, MathPayload, ResultItem
from src.presentation.matrix_editor import MatrixEditor


def test_matrix_copy_to_buttons_transfer_results(qtbot):
    """Los botones 'Copiar a A' y 'Copiar a B' cargan resultados en cuadrículas."""
    editor = MatrixEditor()
    qtbot.addWidget(editor)
    editor.show()

    calc = CalculationBlock(
        "success",
        ResultItem(MathPayload("[[10, 20], [30, 40]]", "Matriz"), "Resultado"),
        related_results=[
            ResultItem(MathPayload("[[1, 2], [3, 4]]", "L"), "Factor L"),
            ResultItem(MathPayload("[[5, 6], [7, 8]]", "U"), "Factor U"),
        ],
    )
    editor.set_results(calc)
    assert not editor.results.isHidden()
    assert editor.result_selector.count() == 2

    # Copiar Factor U a Matriz A
    copy_a_btn = editor.findChild(QPushButton, "matrix-copy-to-a")
    assert copy_a_btn is not None
    editor.result_selector.setCurrentIndex(1)  # Factor U
    qtbot.mouseClick(copy_a_btn, Qt.MouseButton.LeftButton)
    assert editor.a.text() == "[[5, 6], [7, 8]]"
    assert editor.tabs.currentWidget() is editor.a

    # Copiar Factor L a Matriz B
    copy_b_btn = editor.findChild(QPushButton, "matrix-copy-to-b")
    assert copy_b_btn is not None
    editor.result_selector.setCurrentIndex(0)  # Factor L
    qtbot.mouseClick(copy_b_btn, Qt.MouseButton.LeftButton)
    assert editor.b.text() == "[[1, 2], [3, 4]]"
    assert editor.tabs.currentWidget() is editor.b


def test_matrix_transfer_buttons_between_grids(qtbot):
    """Los botones 'A → B' y 'B → A' copian el contenido entre cuadrículas."""
    editor = MatrixEditor()
    qtbot.addWidget(editor)

    btn_a_to_b = editor.findChild(QPushButton, "matrix-transfer-a-to-b")
    btn_b_to_a = editor.findChild(QPushButton, "matrix-transfer-b-to-a")
    assert btn_a_to_b is not None
    assert btn_b_to_a is not None

    # Copiar de A hacia B
    editor.a.load("[[9, 8], [7, 6]]")
    qtbot.mouseClick(btn_a_to_b, Qt.MouseButton.LeftButton)
    assert editor.b.text() == "[[9, 8], [7, 6]]"
    assert editor.tabs.currentWidget() is editor.b

    # Modificar B y copiar hacia A
    editor.b.load("[[1, 0], [0, 1]]")
    qtbot.mouseClick(btn_b_to_a, Qt.MouseButton.LeftButton)
    assert editor.a.text() == "[[1, 0], [0, 1]]"
    assert editor.tabs.currentWidget() is editor.a
