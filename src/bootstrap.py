import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlScheme
from PySide6.QtWidgets import QApplication

from src.application.build_math_runtime import build_math_runtime
from src.infrastructure.sqlite_history import SQLiteHistoryRepository
from src.presentation.main_window import MainWindow
from src.presentation.scheme_handler import MathSchemeHandler


def build_application() -> QApplication:
    """
    Construye y devuelve la aplicación PySide6 con todas
    sus dependencias inyectadas.
    """
    # 0. Registrar esquema local seguro ANTES de crear QApplication
    scheme = QWebEngineUrlScheme(b"math")
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)

    app = QApplication(sys.argv)

    # Instalar manejador en el perfil por defecto
    profile = QWebEngineProfile.defaultProfile()
    handler = MathSchemeHandler(profile)
    profile.installUrlSchemeHandler(b"math", handler)

    app.setApplicationName("CalculadoraSuperInteligente")
    data_dir = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    history = SQLiteHistoryRepository(str(data_dir / "history.sqlite3"))

    use_case = build_math_runtime()
    main_window = MainWindow(use_case, history, use_case.parser)
    main_window.show()

    # Asociamos la ventana principal a la app para evitar recolección de basura
    app.main_window = main_window

    return app
