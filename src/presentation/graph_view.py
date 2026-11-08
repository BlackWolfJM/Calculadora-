import base64
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QFile, QIODevice, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from src.presentation import theme


class _ViewportBridge(QObject):
    changed = Signal(object, object)

    @Slot(float, float, float, float)
    def viewportChanged(
        self, x_min: float, x_max: float, y_min: float, y_max: float
    ) -> None:
        if (
            all(math.isfinite(value) for value in (x_min, x_max, y_min, y_max))
            and x_min < x_max
            and y_min < y_max
        ):
            self.changed.emit((x_min, x_max), (y_min, y_max))


class GraphView(QWebEngineView):
    """
    Componente para renderizar gráficas interactivas con Plotly offline.
    """

    viewport_changed = Signal(object, object)

    def __init__(
        self, parent: QWidget | None = None, *, workspace: bool = False
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._loaded = False
        self._pending_traces: list[dict[str, Any]] = []
        self._pending_workspace: dict[str, Any] | None = None
        self._exporting = False
        self.loadFinished.connect(self._on_loaded)

        # Deshabilitar acceso a archivos remotos por seguridad
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False
        )
        self.page().setBackgroundColor(QColor(theme.SURFACE))

        self.setAccessibleName(
            "Área gráfica interactiva" if workspace else "Gráfica matemática"
        )
        if workspace:
            self._channel = QWebChannel(self.page())
            self._viewport = _ViewportBridge(self._channel)
            self._viewport.changed.connect(self.viewport_changed)
            self._channel.registerObject("viewport", self._viewport)
            self.page().setWebChannel(self._channel)
        self._init_html()

    def _init_html(self) -> None:
        # Cargamos un HTML base con Plotly incluido localmente
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="math://plotly/plotly.min.js"></script>
            __WORKSPACE_SCRIPT__
            <style>
                body, html { margin: 0; padding: 0; width: 100%; height: 100%;
                    overflow: hidden; background-color: __SURFACE__; }
                #plot { width: 100%; height: 100%; }
            </style>
        </head>
        <body data-paper="__SURFACE__" data-ink="__TEXT__"
            data-grid="__BORDER__" data-axis="__MUTED__">
            <div id="plot" tabindex="0" role="region"
                aria-label="Gráfica matemática"></div>
            <script>
                function renderPlot(dataJSON) {
                    var data = JSON.parse(dataJSON).map((trace, i) => ({
                        ...trace,
                        line: {...trace.line,
                               color: i % 2 ? '__SUCCESS__' : '__PRIMARY__',
                               dash: i % 2 ? 'dash' : 'solid', width: 2.5}
                    }));

                    var layout = {
                        margin: { t: 16, r: 20, b: 65, l: 55 },
                        paper_bgcolor: '__SURFACE__',
                        plot_bgcolor: '__SURFACE__',
                        font: { color: '__TEXT__', family: 'Segoe UI', size: 13 },
                        xaxis: { gridcolor: '__BORDER__', zerolinecolor: '__MUTED__' },
                        yaxis: { gridcolor: '__BORDER__', zerolinecolor: '__MUTED__' },
                        showlegend: true,
                        legend: { x: 0, y: -0.22, orientation: 'h' },
                        colorway: ['__PRIMARY__', '__SUCCESS__']
                    };

                    Plotly.newPlot('plot', data, layout, {responsive: true,
                        displaylogo: false,
                        toImageButtonOptions: {format: 'png'}});
                }
            </script>
        </body>
        </html>
        """
        for token, color in {
            "__SURFACE__": theme.SURFACE,
            "__TEXT__": theme.TEXT,
            "__BORDER__": theme.SURFACE_ALT,
            "__MUTED__": theme.MUTED,
            "__PRIMARY__": theme.PRIMARY,
            "__SUCCESS__": theme.SUCCESS,
        }.items():
            html = html.replace(token, color)
        scripts = ""
        if self._workspace:
            library = QFile(":/qtwebchannel/qwebchannel.js")
            if library.open(QIODevice.OpenModeFlag.ReadOnly):
                source = library.readAll().data().decode("utf-8")
                scripts = f"<script>{source}</script>"
            scripts += '<script src="math://plotly/workspace_plot.js"></script>'
        html = html.replace("__WORKSPACE_SCRIPT__", scripts)
        self.setHtml(html, "math://base/")

    def render_graph(self, traces: list[dict[str, Any]]) -> None:
        """
        Dibuja la gráfica inyectando el JSON a través de JavaScript.
        `traces` es una lista de diccionarios compatibles con Plotly.
        """
        self._pending_traces = traces
        if self._loaded:
            self.page().runJavaScript(
                f"renderPlot({json.dumps(json.dumps(traces, allow_nan=False))});"
            )

    def _on_loaded(self, ok: bool) -> None:
        self._loaded = ok
        if ok:
            if self._workspace:
                self._flush_workspace()
            else:
                self.render_graph(self._pending_traces)

    def render_workspace(
        self,
        traces: list[dict[str, Any]],
        *,
        view: str,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        revision: int,
    ) -> None:
        self._pending_workspace = {
            "traces": traces,
            "view": view,
            "xRange": x_range,
            "yRange": y_range,
            "revision": revision,
        }
        self._flush_workspace()

    def _flush_workspace(self) -> None:
        if self._loaded and self._pending_workspace is not None:
            payload = json.dumps(self._pending_workspace, allow_nan=False)
            self.page().runJavaScript(f"renderWorkspace({json.dumps(payload)});")

    def export_png(self, path: str, on_error: Callable[[str], None]) -> None:
        if self._exporting:
            on_error("Ya hay una exportación en curso.")
            return
        if not self._loaded or self._pending_workspace is None:
            on_error("Espera a que la gráfica termine de cargar.")
            return
        self._exporting = True
        self.page().runJavaScript("startWorkspacePng();")
        self._read_png(Path(path), on_error, attempts=100)

    def _read_png(
        self, path: Path, on_error: Callable[[str], None], attempts: int
    ) -> None:
        def handle(result: object) -> None:
            if result == "pending" and attempts:
                QTimer.singleShot(
                    100, self, lambda: self._read_png(path, on_error, attempts - 1)
                )
                return
            self._exporting = False
            prefix = "data:image/png;base64,"
            if not isinstance(result, str) or not result.startswith(prefix):
                on_error("No se pudo generar la imagen de la gráfica.")
                return
            try:
                path.write_bytes(base64.b64decode(result[len(prefix) :], validate=True))
            except (OSError, ValueError):
                on_error("No se pudo escribir el archivo PNG.")

        self.page().runJavaScript(
            """(() => {
                const result = window.workspacePng;
                if (result !== "pending") delete window.workspacePng;
                return result;
            })()""",
            handle,
        )
