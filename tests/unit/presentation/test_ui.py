"""
Test de inicialización de la ventana principal.

Maneja destrucción determinista de QWebEngineView para evitar
el crash 0xC0000005 durante el teardown de QApplication en Windows.
"""

from PySide6.QtCore import QCoreApplication, QEvent

from src.application.solve_expression import SolveExpressionUseCase
from src.domain.modules.derivatives.module import DerivativesModule
from src.domain.modules.integrals.module import IntegralsModule
from src.domain.registry import ModuleRegistry
from src.domain.verification import MathVerifier
from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sqlite_history import SQLiteHistoryRepository
from src.infrastructure.sympy_adapter import SympyAdapter
from src.presentation.main_window import MainWindow


def test_main_window_initialization(qtbot):
    """La ventana se inicializa con sus dependencias reales."""
    adapter = SympyAdapter()
    parser = MathParser()
    history = SQLiteHistoryRepository(":memory:")
    derivatives_module = DerivativesModule(adapter)
    integrals_module = IntegralsModule(adapter)

    registry = ModuleRegistry()
    registry.register(derivatives_module)
    registry.register(integrals_module)

    verifier = MathVerifier()
    use_case = SolveExpressionUseCase(parser, registry, verifier)

    window = MainWindow(use_case, history, parser)
    qtbot.addWidget(window)

    # Verificaciones básicas de los widgets de la UI
    assert window.windowTitle() == "Calculadora Súper Inteligente"
    assert window.input_editor is not None
    assert window.btn_solve is not None
    assert window.btn_solve.text() == "Resolver"
    assert window.result_area is not None

    # --- Destrucción determinista de QWebEngineView ---
    # QWebEngineView y su perfil/páginas deben destruirse ANTES de que
    # QApplication se destruya. Si no, Chromium crashea con 0xC0000005.
    # qtbot.addWidget registra la destrucción, pero no controla el orden
    # respecto a QWebEngineProfile/QWebEnginePage.

    # 1. Shutdown del controlador de procesos
    window.worker_controller.shutdown()

    # 2. Destruir explícitamente las vistas web (MathView, GraphView)
    #    que contienen QWebEnginePage con referencias a QWebEngineProfile
    if hasattr(window, "result_area") and window.result_area:
        window.result_area.setParent(None)
        window.result_area.deleteLater()

    if hasattr(window, "interpretation_math") and window.interpretation_math:
        window.interpretation_math.setParent(None)
        window.interpretation_math.deleteLater()

    if hasattr(window, "graph_view") and window.graph_view:
        window.graph_view.setParent(None)
        window.graph_view.deleteLater()

    # 3. Procesar eventos pendientes para que deleteLater se ejecute
    app = QCoreApplication.instance()
    if app:
        app.processEvents()

    # 4. Cerrar la ventana antes del teardown de pytest-qt
    window.close()
    window.deleteLater()
    if app:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
