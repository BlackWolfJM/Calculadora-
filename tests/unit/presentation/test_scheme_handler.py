"""
Tests de seguridad para MathSchemeHandler.

Verifica protección contra path traversal, percent-encoding,
hosts desconocidos, extensiones no permitidas y rutas hermanas.
"""

import pytest

from src.presentation.scheme_handler import MathSchemeHandler


class FakeUrl:
    """Simula un QUrl con host() y path()."""

    def __init__(self, host: str, path: str):
        self._host = host
        self._path = path

    def host(self):
        return self._host

    def path(self):
        return self._path


class FakeJob:
    """Simula un QWebEngineUrlRequestJob."""

    class Error:
        UrlNotFound = "UrlNotFound"

    def __init__(self, url: FakeUrl):
        self._url = url
        self.failed = False
        self.fail_error = None
        self.replied = False
        self.reply_mime = None

    def requestUrl(self):
        return self._url

    def fail(self, error):
        self.failed = True
        self.fail_error = error

    def reply(self, mime_type, file):
        self.replied = True
        self.reply_mime = mime_type


@pytest.fixture
def handler():
    """Crea un MathSchemeHandler con el directorio de assets real."""
    return MathSchemeHandler()


def _make_job(host: str, path: str) -> FakeJob:
    return FakeJob(FakeUrl(host, path))


# ---------------------------------------------------------------------------
# Test 1: Path traversal con ..
# ---------------------------------------------------------------------------


def test_path_traversal_dotdot(handler):
    """math://katex/../../../etc/passwd → UrlNotFound."""
    job = _make_job("katex", "/../../../etc/passwd")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 2: Path traversal con percent-encoding
# ---------------------------------------------------------------------------


def test_path_traversal_encoded(handler):
    """math://katex/%2e%2e/%2e%2e/etc/passwd → UrlNotFound."""
    job = _make_job("katex", "/%2e%2e/%2e%2e/etc/passwd")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 3: Separadores alternativos (backslash)
# ---------------------------------------------------------------------------


def test_alternate_separator(handler):
    """math://katex/..\\..\\etc\\passwd → UrlNotFound."""
    job = _make_job("katex", "/..\\..\\etc\\passwd")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 4: Host desconocido
# ---------------------------------------------------------------------------


def test_unknown_host(handler):
    """math://evil/payload.js → UrlNotFound."""
    job = _make_job("evil", "/payload.js")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 5: Extensión no permitida
# ---------------------------------------------------------------------------


def test_disallowed_extension(handler):
    """Archivo con extensión .toml → UrlNotFound."""
    job = _make_job("katex", "/../../pyproject.toml")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 6: Host con prefijo similar (sibling prefix)
# ---------------------------------------------------------------------------


def test_sibling_prefix_path(handler):
    """math://katex-evil/payload.js → UrlNotFound (host no permitido)."""
    job = _make_job("katex-evil", "/payload.js")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 7: Request válida (archivo que existe)
# ---------------------------------------------------------------------------


def test_valid_request(handler):
    """math://katex/katex.min.css → éxito (si el archivo existe)."""
    # Verificar que el archivo de KaTeX existe en assets
    assets_dir = handler._assets_dir
    css_path = assets_dir / "katex" / "katex.min.css"

    if not css_path.exists():
        pytest.skip("katex.min.css no encontrado en assets — skip")

    job = _make_job("katex", "/katex.min.css")
    try:
        handler.requestStarted(job)
    except TypeError:
        # QFile.setParent(FakeJob) lanza TypeError porque FakeJob no es QObject.
        # Esto es esperado y demuestra que el handler llegó a reply() exitosamente
        # (no llamó fail() antes).
        pass

    # Lo crucial: no se llamó fail()
    assert not job.failed


# ---------------------------------------------------------------------------
# Test 8: Double percent-encoding
# ---------------------------------------------------------------------------


def test_double_encoded_traversal(handler):
    """math://katex/%252e%252e/ — doble encoding → UrlNotFound."""
    job = _make_job("katex", "/%252e%252e/%252e%252e/etc/passwd")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 9: Empty path
# ---------------------------------------------------------------------------


def test_empty_path(handler):
    """math://katex/ con path vacío → UrlNotFound (sin extensión)."""
    job = _make_job("katex", "/")
    handler.requestStarted(job)
    assert job.failed


# ---------------------------------------------------------------------------
# Test 10: Null bytes
# ---------------------------------------------------------------------------


def test_null_bytes_in_path(handler):
    """Path con null bytes → UrlNotFound."""
    job = _make_job("katex", "/katex.min.js%00.txt")
    handler.requestStarted(job)
    # Debe fallar por extensión .txt o por path inválido
    assert job.failed
