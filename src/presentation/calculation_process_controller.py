"""
CalculationProcessController — Controlador robusto de procesos de cálculo.

Gestiona el ciclo de vida de un proceso hijo (spawn) que ejecuta
el motor matemático, con rollback seguro, shutdown idempotente
y señalización determinista.
"""

import multiprocessing
import time
import uuid
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from src.domain.responses import ResolutionStatus, SolutionResponse
from src.infrastructure.calculation_worker import deserialize_response

# ---------------------------------------------------------------------------
# Protocolos para inyección de dependencias
# ---------------------------------------------------------------------------


class ProcessHandle(Protocol):
    """Interfaz mínima que debe cumplir un objeto 'proceso'."""

    pid: Optional[int]
    exitcode: Optional[int]

    def start(self) -> None: ...
    def is_alive(self) -> bool: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def join(self, timeout: float | None = None) -> None: ...
    def close(self) -> None: ...


class PipeEnd(Protocol):
    """Interfaz mínima que debe cumplir un extremo de pipe."""

    def poll(self, timeout: float = 0) -> bool: ...
    def recv(self) -> Any: ...
    def close(self) -> None: ...


class ProcessState(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


# ---------------------------------------------------------------------------
# Factoría por defecto (multiprocessing real)
# ---------------------------------------------------------------------------


def _default_context_factory():
    """Devuelve el contexto 'spawn' real de multiprocessing."""
    return multiprocessing.get_context("spawn")


# ---------------------------------------------------------------------------
# Controlador
# ---------------------------------------------------------------------------


class CalculationProcessController(QObject):
    finished_calculation = Signal(SolutionResponse)
    error_occurred = Signal(str)
    idle = Signal()
    state_changed = Signal(object)  # Envía ProcessState

    # Límite de iteraciones al vaciar mensajes pendientes
    _MAX_DRAIN_ITERATIONS = 16

    def __init__(
        self,
        timeout_ms: int = 15000,
        process_target: Any = None,
        context_factory: Callable | None = None,
        clock: Callable[[], float] | None = None,
    ):
        super().__init__()
        self.timeout_ms = timeout_ms

        if process_target is None:
            from src.infrastructure.calculation_worker import run_calculation_process

            self.process_target = run_calculation_process
        else:
            self.process_target = process_target

        self._context_factory = context_factory or _default_context_factory
        self._clock = clock or time.monotonic

        self.process: Optional[Any] = None
        self.parent_pipe: Optional[Any] = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_process)
        self.start_time: float = 0
        self.current_request_id: Optional[str] = None
        self._is_cancelled = False
        self._state = ProcessState.IDLE
        self._shutting_down = False

        # Flags para evitar llamadas repetidas a terminate/kill
        self._terminated = False
        self._killed = False

        # Diagnósticos
        self.last_pid: Optional[int] = None
        self.last_exitcode: Optional[int] = None
        self.last_process_closed = False

        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self._monitor_cleanup)
        self.process_to_clean: Optional[Any] = None
        self.cleanup_timeout_start: float = 0
        self.cleanup_mode = "graceful"

    # ----- Estado -----

    def _set_state(self, state: ProcessState) -> None:
        if self._state != state:
            self._state = state
            if not self._shutting_down:
                self.state_changed.emit(state)
                if state == ProcessState.IDLE:
                    self.idle.emit()

    # ----- Arranque -----

    def start(self, expression: str, module_id: str, parameters: dict) -> bool:
        if self._state != ProcessState.IDLE or self._shutting_down:
            return False

        self._set_state(ProcessState.RUNNING)
        request_id = str(uuid.uuid4())
        self.current_request_id = request_id
        self._is_cancelled = False
        self._terminated = False
        self._killed = False

        parent_pipe = None
        child_pipe = None
        process = None

        try:
            ctx = self._context_factory()
            parent_pipe, child_pipe = ctx.Pipe(duplex=False)
            process = ctx.Process(
                target=self.process_target,
                args=(request_id, expression, module_id, parameters, child_pipe),
            )
            process.start()

            # Todo OK — asignar a self
            self.parent_pipe = parent_pipe
            self.process = process
            self.last_pid = getattr(process, "pid", None)
            self.last_process_closed = False
            self.last_exitcode = None

        except Exception:
            # Rollback: cerrar todo lo parcialmente creado
            if child_pipe is not None:
                try:
                    child_pipe.close()
                except Exception:
                    pass
            if parent_pipe is not None:
                try:
                    parent_pipe.close()
                except Exception:
                    pass
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    process.join(timeout=1.0)
                except Exception:
                    pass
                try:
                    process.close()
                except Exception:
                    pass

            self.process = None
            self.parent_pipe = None

            # Emitir FAILED conservando el request_id
            self._set_state(ProcessState.STOPPING)
            resp = SolutionResponse(
                response_id=request_id,
                status=ResolutionStatus.FAILED,
                error="Fallo al iniciar el proceso matemático.",
            )
            self.finished_calculation.emit(resp)
            self._set_state(ProcessState.IDLE)
            return False

        # Cerrar el extremo hijo en el padre
        if child_pipe is not None:
            try:
                child_pipe.close()
            except Exception:
                pass

        self.start_time = self._clock()
        self.timer.start(50)
        return True

    # ----- Cancelación -----

    def cancel(self) -> None:
        if not self.current_request_id or self._shutting_down:
            return

        self._is_cancelled = True

        # Vaciar mensajes pendientes con límite acotado
        if self.parent_pipe:
            for _ in range(self._MAX_DRAIN_ITERATIONS):
                try:
                    if not self.parent_pipe.poll():
                        break
                except (EOFError, BrokenPipeError, OSError):
                    break
                try:
                    self.parent_pipe.recv()
                except (EOFError, BrokenPipeError, OSError):
                    break

        # Emitir CANCELLED una sola vez (si estaba en RUNNING)
        if self._state == ProcessState.RUNNING:
            self._set_state(ProcessState.STOPPING)
            resp = SolutionResponse(
                response_id=self.current_request_id,
                status=ResolutionStatus.CANCELLED,
                error="Cálculo cancelado por el usuario.",
            )
            self.finished_calculation.emit(resp)
            self.retire_async(mode="immediate")

    # ----- Polling -----

    def _check_process(self) -> None:
        if (
            not self.process
            or self._state != ProcessState.RUNNING
            or self._shutting_down
        ):
            return

        # Comprobar mensajes
        pipe_ready = False
        if self.parent_pipe:
            try:
                pipe_ready = self.parent_pipe.poll()
            except (EOFError, BrokenPipeError, OSError):
                if not self._is_cancelled:
                    self._emit_terminal_once(
                        ResolutionStatus.FAILED, "Error de tubería IPC (poll)."
                    )
                return

        if pipe_ready:
            try:
                msg = self.parent_pipe.recv()
                if self._is_cancelled:
                    return  # Ya procesado por cancel()

                if not isinstance(msg, dict) or msg.get("schema_version") != 1:
                    self._emit_terminal_once(
                        ResolutionStatus.FAILED,
                        "Versión de IPC inválida o desconocida.",
                    )
                    return

                if msg.get("success"):
                    resp = deserialize_response(msg["data"])
                    if resp.response_id == self.current_request_id:
                        self._set_state(ProcessState.STOPPING)
                        self.finished_calculation.emit(resp)
                        self.retire_async(mode="graceful")
                    # Si response_id no coincide, se ignora (respuesta obsoleta)
                else:
                    req_id = msg.get("request_id")
                    if req_id == self.current_request_id:
                        self._emit_terminal_once(
                            ResolutionStatus.FAILED,
                            "Error interno controlado del motor matemático.",
                        )
            except (EOFError, BrokenPipeError, OSError):
                if not self._is_cancelled:
                    self._emit_terminal_once(
                        ResolutionStatus.FAILED, "Error de tubería IPC."
                    )
            except Exception:
                if not self._is_cancelled:
                    self._emit_terminal_once(
                        ResolutionStatus.FAILED, "Payload de IPC corrupto."
                    )
            return

        # Timeout
        elapsed = (self._clock() - self.start_time) * 1000
        if elapsed > self.timeout_ms:
            if not self._is_cancelled:
                self._emit_terminal_once(
                    ResolutionStatus.TIMEOUT, "El cálculo excedió el límite de tiempo."
                )
            return

        # Muerte prematura
        if not self.process.is_alive() and not (self.parent_pipe and self._safe_poll()):
            if not self._is_cancelled:
                self._emit_terminal_once(
                    ResolutionStatus.FAILED, "El proceso terminó inesperadamente."
                )
            return

    def _safe_poll(self) -> bool:
        """poll() sin propagar excepciones."""
        try:
            return self.parent_pipe.poll()
        except (EOFError, BrokenPipeError, OSError):
            return False

    def _emit_terminal_once(self, status: ResolutionStatus, error_msg: str) -> None:
        if self._state == ProcessState.RUNNING:
            self._set_state(ProcessState.STOPPING)
            resp = SolutionResponse(
                response_id=self.current_request_id or "",
                status=status,
                error=error_msg,
            )
            self.finished_calculation.emit(resp)
            mode = (
                "immediate"
                if status
                in (
                    ResolutionStatus.CANCELLED,
                    ResolutionStatus.TIMEOUT,
                    ResolutionStatus.FAILED,
                )
                else "graceful"
            )
            self.retire_async(mode=mode)

    # ----- Limpieza asíncrona -----

    def retire_async(self, mode: str = "graceful") -> None:
        self.timer.stop()
        if self.process:
            if mode == "immediate" and self.process.is_alive():
                self._safe_terminate(self.process)

            self.process_to_clean = self.process
            self.process = None
            self.cleanup_mode = mode
            self.cleanup_timeout_start = self._clock()
            self.cleanup_timer.start(100)
        else:
            self._finalize_cleanup()

    def _monitor_cleanup(self) -> None:
        if not self.process_to_clean:
            self.cleanup_timer.stop()
            self._finalize_cleanup()
            return

        if not self.process_to_clean.is_alive():
            self._close_process_safely(self.process_to_clean)
            self.process_to_clean = None
            self.cleanup_timer.stop()
            self._finalize_cleanup()
            return

        elapsed = self._clock() - self.cleanup_timeout_start
        if self.cleanup_mode == "graceful" and elapsed > 0.5:
            self._safe_terminate(self.process_to_clean)
            self.cleanup_mode = "immediate"
            self.cleanup_timeout_start = self._clock()
        elif self.cleanup_mode == "immediate" and elapsed > 1.0:
            self._safe_kill(self.process_to_clean)
            # Seguimos monitoreando hasta is_alive() == False

    def _finalize_cleanup(self) -> None:
        if self.parent_pipe:
            try:
                self.parent_pipe.close()
            except Exception:
                pass
            self.parent_pipe = None
        self.current_request_id = None
        self._set_state(ProcessState.IDLE)

    def _close_process_safely(self, p: Any) -> None:
        try:
            p.join(timeout=0)
            self.last_exitcode = p.exitcode
            p.close()
            self.last_process_closed = True
        except (ValueError, OSError):
            raise RuntimeError("No se pudo cerrar el handle del proceso.") from None

    # ----- Helpers de terminate/kill una sola vez -----

    def _safe_terminate(self, p: Any) -> None:
        if not self._terminated:
            self._terminated = True
            try:
                p.terminate()
            except (OSError, ValueError):
                pass

    def _safe_kill(self, p: Any) -> None:
        if not self._killed:
            self._killed = True
            try:
                p.kill()
            except (OSError, ValueError):
                pass

    # ----- Shutdown -----

    def shutdown(self) -> None:
        """Shutdown idempotente. No emite señales de UI."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self.timer.stop()
        self.cleanup_timer.stop()

        p = self.process or self.process_to_clean

        if p:
            try:
                if p.is_alive():
                    try:
                        p.terminate()
                    except (OSError, ValueError):
                        pass
                    p.join(timeout=1.0)

                    if p.is_alive():
                        try:
                            p.kill()
                        except (OSError, ValueError):
                            pass
                        p.join(timeout=1.0)

                    if p.is_alive():
                        raise RuntimeError(
                            f"shutdown(): el proceso PID={getattr(p, 'pid', '?')} "
                            "sigue vivo tras terminate+kill+2s de join."
                        )

                # Proceso muerto — join final y close
                self._close_process_safely(p)
            except RuntimeError:
                self._shutting_down = False
                if self.parent_pipe:
                    self.parent_pipe.close()
                    self.parent_pipe = None
                raise
            except Exception as exc:
                self._shutting_down = False
                raise RuntimeError(
                    "No se pudo confirmar el cierre del proceso."
                ) from exc

        self.process = None
        self.process_to_clean = None
        # Cerrar pipe siempre
        if self.parent_pipe:
            try:
                self.parent_pipe.close()
            except Exception:
                pass
            self.parent_pipe = None

        self.current_request_id = None
        # No emitimos state_changed/idle durante shutdown (flag _shutting_down)
        self._state = ProcessState.IDLE
