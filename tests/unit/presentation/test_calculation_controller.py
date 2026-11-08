"""
Tests exhaustivos para CalculationProcessController.

Usa fakes inyectados (FakeContextFactory, FakePipe, FakeProcess) para
pruebas de lógica, y el spawn real para pruebas E2E.
"""

import os

import pytest

from src.domain.errors import StructuredMathError
from src.domain.responses import ResolutionStatus, SolutionResponse
from src.infrastructure.calculation_worker import (
    deserialize_response,
    serialize_response,
)
from src.presentation.calculation_process_controller import (
    CalculationProcessController,
    ProcessState,
)

# ---------------------------------------------------------------------------
# Fakes inyectables (sin monkeypatch de globales)
# ---------------------------------------------------------------------------


class FakePipe:
    """Simula un extremo de pipe con cola de mensajes controlable."""

    def __init__(self):
        self._messages: list = []
        self._closed = False
        self._poll_error: Exception | None = None
        self._recv_error: Exception | None = None

    def enqueue(self, msg):
        """Añade un mensaje a la cola."""
        self._messages.append(msg)

    def set_poll_error(self, err: Exception):
        self._poll_error = err

    def set_recv_error(self, err: Exception):
        self._recv_error = err

    def poll(self, timeout=0):
        if self._poll_error:
            raise self._poll_error
        return len(self._messages) > 0

    def recv(self):
        if self._recv_error:
            raise self._recv_error
        if self._messages:
            return self._messages.pop(0)
        raise EOFError("pipe vacío")

    def close(self):
        self._closed = True

    @property
    def closed(self):
        return self._closed


class FakeProcess:
    """Simula un proceso con control de is_alive, terminate, kill, etc."""

    def __init__(self, target=None, args=None, **kwargs):
        self.pid = 9999
        self._alive = True
        self.exitcode = None
        self._start_called = False
        self._terminate_called = False
        self._kill_called = False
        self._join_called = False
        self._close_called = False
        self._start_error: Exception | None = None
        self._die_on_terminate = True

    def set_start_error(self, err: Exception):
        self._start_error = err

    def set_die_on_terminate(self, val: bool):
        self._die_on_terminate = val

    def start(self):
        if self._start_error:
            raise self._start_error
        self._start_called = True

    def is_alive(self):
        return self._alive

    def terminate(self):
        self._terminate_called = True
        if self._die_on_terminate:
            self._alive = False
            self.exitcode = -15

    def kill(self):
        self._kill_called = True
        self._alive = False
        self.exitcode = -9

    def join(self, timeout=None):
        self._join_called = True

    def close(self):
        self._close_called = True


class FakeContext:
    """Contexto que produce FakeProcess en vez de un proceso real."""

    def __init__(self):
        self.last_process: FakeProcess | None = None
        self._process_factory = FakeProcess

    def set_process_factory(self, factory):
        self._process_factory = factory

    def Process(self, target=None, args=None, **kwargs):
        p = self._process_factory(target=target, args=args, **kwargs)
        self.last_process = p
        return p


class FakeContextFactory:
    """Factoría inyectable que devuelve siempre el mismo FakeContext."""

    def __init__(self):
        self.context = FakeContext()
        self._pipes: list[tuple[FakePipe, FakePipe]] = []
        self._parent_pipe = FakePipe()
        self._child_pipe = FakePipe()
        self.context.Pipe = lambda duplex=False: (self._parent_pipe, self._child_pipe)

    def __call__(self):
        return self.context

    @property
    def parent_pipe(self):
        return self._parent_pipe

    @property
    def last_process(self):
        return self.context.last_process


class FakeClock:
    """Reloj controlable para pruebas de timeout."""

    def __init__(self, start: float = 1000.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float):
        self._now += seconds


def _dummy_target(*args, **kwargs):
    """Target que no hace nada (para pruebas con mocks)."""
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_factory():
    return FakeContextFactory()


@pytest.fixture
def fake_clock():
    return FakeClock()


@pytest.fixture
def controller(qtbot, fake_factory, fake_clock):
    """Controller con fakes inyectados."""
    ctrl = CalculationProcessController(
        timeout_ms=5000,
        process_target=_dummy_target,
        context_factory=fake_factory,
        clock=fake_clock,
    )
    yield ctrl
    try:
        ctrl.shutdown()
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Test 1: Codec de StructuredMathError con igualdad completa
# ---------------------------------------------------------------------------


def test_structured_math_error_codec():
    """Serialización y deserialización de StructuredMathError preserva campos."""
    error = StructuredMathError(
        code="ERR_SYNTAX_TOKEN",
        message="Token inesperado '*'",
        line=1,
        column=5,
        end_line=1,
        end_column=6,
        fragment="*",
        suggestion="Verifica la sintaxis",
        internal_cause="lark.UnexpectedToken",
    )
    resp = SolutionResponse(
        response_id="test-123",
        status=ResolutionStatus.INVALID_INPUT,
        error=error.message,
        structured_error=error,
    )
    serialized = serialize_response(resp)
    deserialized = deserialize_response(serialized)

    assert deserialized.status == resp.status
    assert deserialized.response_id == resp.response_id
    assert deserialized.structured_error is not None

    se = deserialized.structured_error
    assert se.code == error.code
    assert se.message == error.message
    assert se.line == error.line
    assert se.column == error.column
    assert se.end_line == error.end_line
    assert se.end_column == error.end_column
    assert se.fragment == error.fragment
    assert se.suggestion == error.suggestion
    assert se.internal_cause == error.internal_cause


# ---------------------------------------------------------------------------
# Test 2: Éxito real con spawn
# ---------------------------------------------------------------------------


def test_success_real_spawn(qtbot):
    """Test E2E real: crea un proceso spawn y obtiene respuesta exitosa."""
    ctrl = CalculationProcessController(timeout_ms=15000)
    try:
        responses = []
        ctrl.finished_calculation.connect(responses.append)

        started = ctrl.start("x^2", "derivatives", {"variable": "x", "order": 1})
        assert started
        assert ctrl._state == ProcessState.RUNNING

        qtbot.waitUntil(lambda: len(responses) > 0, timeout=15000)

        assert responses[0].status == ResolutionStatus.SUCCESS
        assert responses[0].calculation is not None
        assert responses[0].calculation.primary_result is not None
        # La derivada de x^2 respecto a x es 2*x
        result_text = responses[0].calculation.primary_result.value.canonical_text
        assert "2" in result_text and "x" in result_text

        qtbot.waitUntil(lambda: ctrl._state == ProcessState.IDLE, timeout=5000)
    finally:
        try:
            ctrl.shutdown()
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Test 3: Entrada inválida preservando todos los campos del error
# ---------------------------------------------------------------------------


def test_invalid_input_preserves_error_fields(qtbot):
    """Entrada inválida con spawn real preserva StructuredMathError."""
    ctrl = CalculationProcessController(timeout_ms=15000)
    try:
        responses = []
        ctrl.finished_calculation.connect(responses.append)

        started = ctrl.start("x + * 2", "derivatives", {"variable": "x", "order": 1})
        assert started

        qtbot.waitUntil(lambda: len(responses) > 0, timeout=15000)

        resp = responses[0]
        assert resp.status == ResolutionStatus.INVALID_INPUT
        assert resp.structured_error is not None
        assert resp.structured_error.code == "ERR_SYNTAX_TOKEN"
        assert resp.structured_error.line >= 1
        assert resp.structured_error.column >= 1
        assert resp.structured_error.fragment != ""
    finally:
        try:
            ctrl.shutdown()
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Test 4: Cancelación con mensaje pendiente
# ---------------------------------------------------------------------------


def test_cancel_with_pending_message(controller, fake_factory, qtbot):
    """Cancelar con un mensaje pendiente en el pipe lo descarta."""
    parent_pipe = fake_factory.parent_pipe
    parent_pipe.enqueue(
        {
            "schema_version": 1,
            "success": True,
            "data": serialize_response(
                SolutionResponse(
                    response_id="will-be-set",
                    status=ResolutionStatus.SUCCESS,
                )
            ),
        }
    )

    started = controller.start("x", "dummy", {})
    assert started

    # El pipe ya tiene un mensaje, pero cancelamos primero
    responses = []
    controller.finished_calculation.connect(responses.append)
    controller.cancel()

    # Solo debe haber respuesta CANCELLED, no SUCCESS
    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.CANCELLED


# ---------------------------------------------------------------------------
# Test 5: TIMEOUT emitido exactamente una vez
# ---------------------------------------------------------------------------


def test_timeout_emitted_once(controller, fake_factory, fake_clock, qtbot):
    """TIMEOUT se emite exactamente una vez incluso con múltiples checks."""
    controller.timeout_ms = 100
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    # Avanzar el reloj más allá del timeout
    fake_clock.advance(1.0)  # 1000ms > 100ms

    # Llamar _check_process múltiples veces
    controller._check_process()
    controller._check_process()
    controller._check_process()

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.TIMEOUT


# ---------------------------------------------------------------------------
# Test 6: CANCELLED emitido exactamente una vez
# ---------------------------------------------------------------------------


def test_cancelled_emitted_once(controller, fake_factory, qtbot):
    """CANCELLED se emite exactamente una vez al cancelar múltiples veces."""
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    controller.cancel()
    controller.cancel()
    controller.cancel()

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.CANCELLED


# ---------------------------------------------------------------------------
# Test 7: FAILED emitido exactamente una vez
# ---------------------------------------------------------------------------


def test_failed_emitted_once(controller, fake_factory, fake_clock, qtbot):
    """FAILED se emite exactamente una vez ante pipe roto."""
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    fake_factory.parent_pipe.set_poll_error(BrokenPipeError("pipe roto"))

    controller._check_process()
    controller._check_process()

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.FAILED


# ---------------------------------------------------------------------------
# Test 8: Respuesta obsoleta ignorada
# ---------------------------------------------------------------------------


def test_stale_response_ignored(controller, fake_factory, qtbot):
    """Una respuesta con response_id diferente es ignorada."""
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    # Enqueue una respuesta con ID diferente
    fake_factory.parent_pipe.enqueue(
        {
            "schema_version": 1,
            "success": True,
            "data": serialize_response(
                SolutionResponse(
                    response_id="stale-old-id",
                    status=ResolutionStatus.SUCCESS,
                )
            ),
        }
    )

    controller._check_process()

    # No debe haberse emitido finished_calculation
    assert len(responses) == 0
    assert controller._state == ProcessState.RUNNING


# ---------------------------------------------------------------------------
# Test 9: Versión IPC desconocida
# ---------------------------------------------------------------------------


def test_unknown_ipc_version(controller, fake_factory, qtbot):
    """Un mensaje con schema_version != 1 emite FAILED."""
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    fake_factory.parent_pipe.enqueue({"schema_version": 99, "success": True})

    controller._check_process()

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.FAILED
    assert "IPC" in responses[0].error


# ---------------------------------------------------------------------------
# Test 10: Pipe roto (recv lanza EOFError)
# ---------------------------------------------------------------------------


def test_broken_pipe(controller, fake_factory, qtbot):
    """EOFError en recv emite FAILED."""
    started = controller.start("x", "dummy", {})
    assert started

    responses = []
    controller.finished_calculation.connect(responses.append)

    # Hay datos pero recv falla
    fake_factory.parent_pipe.enqueue("dummy")
    fake_factory.parent_pipe.set_recv_error(EOFError("pipe cerrado"))

    controller._check_process()

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.FAILED


# ---------------------------------------------------------------------------
# Test 11: Escalada terminate → kill
# ---------------------------------------------------------------------------


def test_terminate_then_kill_escalation(controller, fake_factory, fake_clock, qtbot):
    """Si terminate no mata al proceso, se escala a kill."""
    started = controller.start("x", "dummy", {})
    assert started

    # Configurar el proceso para que no muera con terminate
    proc = fake_factory.last_process
    proc.set_die_on_terminate(False)

    # Emitir timeout para forzar retire_async(immediate)
    controller.timeout_ms = 100
    fake_clock.advance(1.0)
    controller._check_process()

    # Ahora estamos en cleanup. El proceso sigue vivo.
    assert controller.process_to_clean is not None

    # Simular paso del tiempo en cleanup
    fake_clock.advance(0.6)  # > 0.5s, pero mode ya es immediate por retire_async
    controller._monitor_cleanup()

    # Aún sigue vivo, avanzar más para kill
    fake_clock.advance(1.1)  # > 1.0s
    controller._monitor_cleanup()

    assert proc._kill_called


# ---------------------------------------------------------------------------
# Test 12: start() rechazado en STOPPING
# ---------------------------------------------------------------------------


def test_start_rejected_in_stopping(controller, fake_factory, fake_clock, qtbot):
    """start() retorna False cuando el estado es STOPPING."""
    started = controller.start("x", "dummy", {})
    assert started

    # Forzar STOPPING via timeout
    controller.timeout_ms = 100
    fake_clock.advance(1.0)
    controller._check_process()
    assert controller._state == ProcessState.STOPPING

    # Intentar nuevo start
    result = controller.start("y", "dummy", {})
    assert result is False


# ---------------------------------------------------------------------------
# Test 13: Nuevo cálculo después de cancelación
# ---------------------------------------------------------------------------


def test_new_calculation_after_cancel(controller, fake_factory, fake_clock, qtbot):
    """Después de cancelar, un nuevo cálculo puede arrancarse tras IDLE."""
    started = controller.start("x", "dummy", {})
    assert started
    controller.cancel()

    # Esperar a que llegue a IDLE
    qtbot.waitUntil(lambda: controller._state == ProcessState.IDLE, timeout=3000)

    # Nuevo cálculo
    started2 = controller.start("y", "dummy", {})
    assert started2
    assert controller._state == ProcessState.RUNNING


# ---------------------------------------------------------------------------
# Test 14: Fallo de Process.start()
# ---------------------------------------------------------------------------


def test_process_start_failure(controller, fake_factory, qtbot):
    """Si Process.start() lanza excepción, hace rollback completo."""

    # Configurar el siguiente proceso para que falle en start
    def failing_factory(**kwargs):
        p = FakeProcess(**kwargs)
        p.set_start_error(OSError("No se puede crear proceso"))
        return p

    fake_factory.context.set_process_factory(failing_factory)

    responses = []
    controller.finished_calculation.connect(responses.append)

    result = controller.start("x", "dummy", {})
    assert result is False

    assert len(responses) == 1
    assert responses[0].status == ResolutionStatus.FAILED
    assert responses[0].response_id != ""  # request_id preservado
    assert controller._state == ProcessState.IDLE
    assert controller.process is None
    assert controller.parent_pipe is None or fake_factory.parent_pipe.closed


# ---------------------------------------------------------------------------
# Test 15: Shutdown idempotente
# ---------------------------------------------------------------------------


def test_shutdown_idempotent(controller, fake_factory, qtbot):
    """Llamar shutdown() dos veces no lanza excepción."""
    started = controller.start("x", "dummy", {})
    assert started

    controller.shutdown()
    controller.shutdown()  # Segunda llamada — no debe lanzar

    assert controller._state == ProcessState.IDLE


# ---------------------------------------------------------------------------
# Test 16: No queda proceso vivo (comprobación por PID)
# ---------------------------------------------------------------------------


def test_no_zombie_process_by_pid(qtbot):
    """Verificar que el proceso real muere tras shutdown."""
    ctrl = CalculationProcessController(timeout_ms=15000)
    try:
        responses = []
        ctrl.finished_calculation.connect(responses.append)

        started = ctrl.start("x^2", "derivatives", {"variable": "x", "order": 1})
        assert started
        pid = ctrl.last_pid
        assert pid is not None

        qtbot.waitUntil(lambda: len(responses) > 0, timeout=15000)
        qtbot.waitUntil(lambda: ctrl._state == ProcessState.IDLE, timeout=5000)

        ctrl.shutdown()

        # Verificar que no existe proceso con ese PID (o al menos no es nuestro)
        import psutil

        assert not psutil.pid_exists(pid) or pid == os.getpid()
    except ImportError:
        # Si psutil no está instalado, verificamos con los diagnósticos internos
        assert ctrl.last_process_closed
        assert ctrl.last_exitcode is not None
    finally:
        try:
            ctrl.shutdown()
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Test 17: join(), close() y cierre de pipes efectivos
# ---------------------------------------------------------------------------


def test_join_close_pipe_called(controller, fake_factory, fake_clock, qtbot):
    """Verifica que join(), close() y cierre de pipes se ejecutan."""
    started = controller.start("x", "dummy", {})
    assert started

    parent_pipe = fake_factory.parent_pipe

    # Forzar FAILED para entrar en cleanup
    fake_factory.parent_pipe.set_poll_error(BrokenPipeError("roto"))
    controller._check_process()

    # Esperar cleanup
    qtbot.waitUntil(lambda: controller._state == ProcessState.IDLE, timeout=3000)

    proc = fake_factory.last_process
    assert proc._join_called
    assert proc._close_called
    assert parent_pipe.closed


# ---------------------------------------------------------------------------
# Test básico: Estado inicial IDLE
# ---------------------------------------------------------------------------


def test_controller_starts_in_idle(controller):
    assert controller._state == ProcessState.IDLE
