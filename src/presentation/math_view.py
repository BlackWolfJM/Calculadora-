import html
import json
import re

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from src.presentation import theme

_INLINE_ASSIGNMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"con u = (.+?) y v = (.+?)\."),
        r"con \\(u = \1\\) y \\(v = \2\\).",
    ),
    (
        re.compile(
            r"Se identifica u = (.+?) como el numerador "
            r"y v = (.+?) como el denominador\."
        ),
        r"Se identifica \\(u = \1\\) como el numerador "
        r"y \\(v = \2\\) como el denominador.",
    ),
    (
        re.compile(r"siendo la función interior u = (.+?), por lo que"),
        r"siendo la función interior \\(u = \1\\), por lo que",
    ),
    (
        re.compile(
            r"Hacemos el cambio de variable u = (.+?)\. "
            r"Entonces, du = \((.+?)\) dx\. "
            r"La integral se transforma en ∫(.+?) du,"
        ),
        r"Hacemos el cambio de variable \\(u = \1\\). "
        r"Entonces, \\(du = (\2)\\,dx\\). "
        r"La integral se transforma en \\(\\int \3\\,du\\),",
    ),
)

_BARE_LATEX_TOKEN = re.compile(
    r"(\\(?:sin|cos|tan|sec|csc|cot|asin|acos|atan|ln|log|exp|sqrt|frac)"
    r"(?:\{\\left\([^)]*\\right\)\}|\{[^{}]*\})+"
    r"|[A-Za-z0-9]+\^\{[^{}]+\})"
)


def _normalize_explanation_delimiters(explanation: str) -> str:
    """Envuelve fragmentos LaTeX de pasos en delimitadores \\(...\\) seguros."""
    if (
        not explanation
        or "\\(" in explanation
        or "<" in explanation
        or ">" in explanation
    ):
        return explanation

    normalized = explanation
    for pattern, replacement in _INLINE_ASSIGNMENTS:
        normalized = pattern.sub(replacement, normalized)

    if "\\(" not in normalized and ("\\" in normalized or "^{" in normalized):
        normalized = _BARE_LATEX_TOKEN.sub(r"\\(\1\\)", normalized)

    return normalized


class MathView(QWebEngineView):
    """Vista web incrustada que renderiza LaTeX utilizando KaTeX offline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_security()
        policy = self.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.setInterval(80)
        self._height_timer.timeout.connect(self._measure_height)
        self.loadFinished.connect(self._on_render_finished)

    def _on_render_finished(self, ok: bool) -> None:
        # No dejar visible una fórmula de la respuesta anterior durante la carga.
        self.show()
        if ok:
            self._height_timer.start()

    def setHtml(self, html_doc: str, base_url: QUrl | str = "") -> None:
        url = QUrl(base_url) if isinstance(base_url, str) else base_url
        super().setHtml(html_doc, url)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._height_timer.start()

    def _measure_height(self) -> None:
        if self.property("math_size") is None:
            self.page().runJavaScript("document.body.scrollHeight", self._fit_height)
        else:
            self.page().runJavaScript(
                "document.getElementById('math')?.scrollHeight",
                self._fit_result_height,
            )

    def _fit_result_height(self, height: object) -> None:
        if isinstance(height, (float, int)):
            self.setFixedHeight(max(64, min(240, int(height) + 24)))

    def _fit_height(self, height: object) -> None:
        if isinstance(height, (float, int)) and height > 0:
            self.setMinimumHeight(max(80, int(height) + 4))

    def _setup_security(self) -> None:
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False
        )

    def render_math(
        self, latex_content: str, display_mode: bool = True, explanation: str = ""
    ) -> None:
        """Renderiza fórmulas y prosa escapada con KaTeX local restringido."""
        self.hide()
        result_size = self.property("math_size")
        size = result_size or theme.STEP_FONT_SIZE
        background = theme.RESULT_SURFACE if result_size else theme.SURFACE
        self.page().setBackgroundColor(QColor(background))
        fallback = html.escape(self.accessibleDescription() or latex_content)
        safe_latex = json.dumps(latex_content).replace("<", chr(92) + "u003c")
        formatted_explanation = _normalize_explanation_delimiters(explanation)
        # Solo los delimitadores matemáticos del contrato se renderizan como LaTeX.
        # La prosa y cualquier HTML se insertan siempre como nodos de texto.
        parts = re.split(r"\\\((.*?)\\\)", formatted_explanation, flags=re.DOTALL)
        safe_parts = json.dumps(parts).replace("<", chr(92) + "u003c")
        document = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <link rel="stylesheet" href="math://katex/katex.min.css">
            <script defer src="math://katex/katex.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 4px;
                    box-sizing: border-box;
                    min-height: {"0" if explanation else "100vh"};
                    background-color: {background};
                    color: {theme.TEXT};
                    display: {"block" if explanation else "flex"};
                    align-items: center;
                    justify-content: left;
                    font-size: {size}px;
                    overflow-x: auto;
                    overflow-y: auto;
                }}
                .katex, .katex * {{
                    font-family: "Cambria Math", "Times New Roman", serif !important;
                }}
                .katex {{ font-size: 1em; }}
                .katex .mathnormal, .katex .mathit {{ font-style: italic; }}
                .katex-display {{ margin: 0; }}
                #math {{ min-width: 0; max-width: 100%; }}
                #explanation {{ font: 15px/1.55 "Segoe UI", sans-serif;
                    margin-bottom: 8px; color: {theme.TEXT}; }}
                #math {{ overflow-x: auto; padding-bottom: 6px; }}
                .subst-u {{
                    background-color: #D1FAE5;
                    color: #065F46;
                    border: 1px solid #6EE7B7;
                    border-radius: 4px;
                    padding: 1px 5px;
                    margin: 0 2px;
                    font-weight: 600;
                }}
                .subst-du {{
                    background-color: #FEF3C7;
                    color: #92400E;
                    border: 1px solid #FCD34D;
                    border-radius: 4px;
                    padding: 1px 5px;
                    margin: 0 2px;
                    font-weight: 600;
                }}
            </style>
        </head>
        <body>
            <div id="explanation"></div>
            <div id="math" aria-label="{fallback}">{fallback}</div>
            <script>
                document.addEventListener("DOMContentLoaded", function() {{
                    const latex = {safe_latex};
                    if (!window.katex) return;
                    const parts = {safe_parts};
                    const prose = document.getElementById("explanation");
                    parts.forEach((part, i) => {{
                        const span = document.createElement("span");
                        span.textContent = part;
                        if (i % 2) {{
                            span.className = "math-seg";
                            const inner = part.slice(2, -2).trim();
                            if (/^(du|dv)\\s*=/.test(inner)) {{
                                span.className = "math-seg subst-du";
                            }} else if (/^(u|v)\\s*=/.test(inner)) {{
                                span.className = "math-seg subst-u";
                            }}
                            katex.render(part, span, {{
                                throwOnError: false, trust: false,
                                maxSize: 20, maxExpand: 1000
                            }});
                        }}
                        prose.appendChild(span);
                    }});
                    if (!{str(bool(explanation)).lower()}) prose.style.display = "none";
                    katex.render(latex, document.getElementById("math"), {{
                        displayMode: {str(display_mode).lower()},
                        throwOnError: false,
                        trust: false,
                        maxSize: 20,
                        maxExpand: 1000
                    }});
                    const fit = () => {{
                        const target = document.getElementById("math");
                        document.body.style.fontSize = "{size}px";
                        const ratio = (window.innerWidth - 12) / target.scrollWidth;
                        if (ratio < 1) document.body.style.fontSize =
                            Math.max({24 if size >= 24 else 18}, {size} * ratio) + "px";
                    }};
                    document.fonts.ready.then(fit);
                    window.addEventListener("resize", fit);
                }});
            </script>
        </body>
        </html>
        """
        self.setHtml(document, "math://katex/")
        if hasattr(self, "_height_timer"):
            QTimer.singleShot(40, self.show)
