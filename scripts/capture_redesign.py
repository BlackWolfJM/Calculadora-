"""Capture comparable native windows using an isolated Qt data path."""

import multiprocessing
import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    variant, evidence = sys.argv[1:3]
    folder = Path(evidence).resolve()
    suffix = os.environ.get("CAPTURE_SUFFIX", "")
    if variant == "before":
        import src.presentation

        src.presentation.__path__.insert(0, str(folder / "baseline/src/presentation"))
    from src.bootstrap import build_application
    from src.presentation.history_dialog import HistoryDialog

    QStandardPaths.setTestModeEnabled(True)
    app = build_application()
    w = app.main_window
    # Use an in-memory repository even when Qt test locations already have data.
    from src.infrastructure.sqlite_history import SQLiteHistoryRepository

    w.history_repo.close()
    w.history_repo = SQLiteHistoryRepository(":memory:")

    def capture(name, widget=w):
        QTest.qWait(350)
        assert widget.grab().save(str(folder / f"{variant}{suffix}-{name}.png"))

    for width, height in ((1180, 760), (820, 600)):
        w.resize(width, height)
        w._new_resolution()
        capture(f"{width}-vacio")
        QTest.keyClicks(w.input_editor, "x^2 + 3x")
        QTest.qWait(400)
        assert w.btn_solve.isEnabled()
        if variant == "before":
            w.btn_solve.click()
        else:
            QTest.keyClick(
                w.input_editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier
            )
        for _ in range(180):
            if w._response is not None and not w.btn_cancel.isVisible():
                break
            QTest.qWait(100)
        assert w._response is not None and w._response.calculation is not None
        formula = []
        for _ in range(50):
            w.result_math.page().runJavaScript(
                "Boolean(document.querySelector('#math .katex'))", formula.append
            )
            QTest.qWait(100)
            if formula and formula[-1]:
                break
        assert formula and formula[-1], "KaTeX did not render"
        capture(f"{width}-resultado")
        w.work_scroll.verticalScrollBar().setValue(
            w.work_scroll.verticalScrollBar().maximum()
        )
        capture(f"{width}-pasos")
        w._new_resolution()
        QTest.keyClicks(w.input_editor, "sin(")
        QTest.qWait(400)
        assert w.error_preview_label.isVisible()
        capture(f"{width}-error")
    dialog = HistoryDialog(w.history_repo, w)
    dialog.setStyleSheet(w.styleSheet())
    dialog.show()
    capture("historial", dialog)
    dialog.close()
    w.close()
    app.processEvents()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
