"""
MathSchemeHandler — Manejador seguro para servir archivos estáticos locales
a través del esquema math:// sin acceso libre al disco.

Endurecido contra path traversal, percent-encoding, hosts desconocidos
y extensiones no permitidas.
"""

import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler


class MathSchemeHandler(QWebEngineUrlSchemeHandler):
    """
    Manejador seguro para servir archivos estáticos locales de KaTeX y Plotly
    a través del esquema math:// sin acceso libre al disco.
    """

    # Hosts permitidos
    ALLOWED_HOSTS = frozenset({"katex", "plotly", "base"})

    # Extensiones permitidas
    ALLOWED_EXTENSIONS = frozenset(
        {
            ".js",
            ".css",
            ".woff",
            ".woff2",
            ".ttf",
            ".html",
            ".htm",
            ".svg",
            ".png",
            ".map",
        }
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        # Directorio seguro donde reside KaTeX y Plotly (src/presentation/assets)
        if hasattr(sys, "_MEIPASS"):
            base_dir = os.path.join(sys._MEIPASS, "src", "presentation")
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        self._assets_dir = Path(base_dir, "assets").resolve()

    def requestStarted(self, job: QWebEngineUrlRequestJob):
        url = job.requestUrl()

        # 1. Validar host
        host = url.host()
        if host not in self.ALLOWED_HOSTS:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        # 2. Decodificar percent-encoding y normalizar path
        raw_path = unquote(url.path())
        if raw_path.startswith("/"):
            raw_path = raw_path[1:]

        # 3. Resolver la ruta completa de forma segura
        try:
            full_path = (self._assets_dir / host / raw_path).resolve()
        except (ValueError, OSError):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        # 4. Validación de path traversal con Path.is_relative_to()
        try:
            if not full_path.is_relative_to(self._assets_dir):
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
        except (ValueError, TypeError):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        # 5. Validar extensión
        ext = full_path.suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        # 6. Abrir y servir el archivo
        full_path_str = str(full_path)
        file = QFile(full_path_str)
        if file.exists() and file.open(QIODevice.ReadOnly):
            mime_type, _ = mimetypes.guess_type(full_path_str)
            if not mime_type:
                if full_path_str.endswith(".js"):
                    mime_type = b"application/javascript"
                else:
                    mime_type = b"application/octet-stream"
            else:
                mime_type = mime_type.encode()

            job.reply(mime_type, file)
            # Vincular el ciclo de vida del archivo al del job
            file.setParent(job)
        else:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
