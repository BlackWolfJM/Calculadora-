import multiprocessing
import os
import sys

# Asegurar que el directorio raíz esté en el PYTHONPATH (útil para PyInstaller)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    multiprocessing.freeze_support()

    if "--self-test" in sys.argv:
        # ------------------------------------------------------------------
        # Self-test headless: NO importar src.main, QtWebEngine ni UI.
        # Crea QCoreApplication + CalculationProcessController y ejecuta
        # una derivada real, verificando el resultado completo.
        # ------------------------------------------------------------------
        import signal

        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        from PySide6.QtCore import QCoreApplication, QTimer

        app = QCoreApplication(sys.argv)

        from src.presentation.calculation_process_controller import (
            CalculationProcessController,
        )

        ctrl = CalculationProcessController(timeout_ms=15000)
        result_holder: dict = {"response": None, "idle_reached": False, "error": None}

        def on_finished(resp):
            result_holder["response"] = resp

        def on_idle():
            result_holder["idle_reached"] = True

        ctrl.finished_calculation.connect(on_finished)
        ctrl.idle.connect(on_idle)

        # Resolver d/dx(x^2) = 2*x
        started = ctrl.start("x^2", "derivatives", {"variable": "x", "order": 1})
        if not started:
            print("SELF_TEST_FAILED: No se pudo iniciar el cálculo", file=sys.stderr)
            ctrl.shutdown()
            sys.exit(1)

        # Timer de seguridad: si no obtenemos resultado en 20s, abortamos
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(lambda: app.quit())
        timeout_timer.start(20000)

        # Timer de polling: verificar si tenemos respuesta + idle
        check_timer = QTimer()

        def check_done():
            if result_holder["response"] is not None and result_holder["idle_reached"]:
                check_timer.stop()
                timeout_timer.stop()
                app.quit()

        check_timer.timeout.connect(check_done)
        check_timer.start(50)

        exit_code = 1
        try:
            app.exec()

            resp = result_holder["response"]
            if resp is None:
                print(
                    "SELF_TEST_FAILED: Timeout — no se recibió respuesta",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Comprobar SUCCESS
            from src.domain.responses import ResolutionStatus

            if resp.status != ResolutionStatus.SUCCESS:
                print(
                    f"SELF_TEST_FAILED: status={resp.status}, error={resp.error}",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Comprobar resultado equivalente a 2*x
            import sympy

            result_text = resp.calculation.primary_result.value.canonical_text
            x = sympy.Symbol("x", real=True)
            expected = 2 * x
            actual = sympy.sympify(result_text, locals={"x": x})
            if sympy.simplify(expected - actual) != 0:
                print(
                    f"SELF_TEST_FAILED: resultado={result_text}, esperado=2*x",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Comprobar pasos educativos
            if resp.procedure is None or not resp.procedure.steps:
                print(
                    "SELF_TEST_FAILED: procedure es None (sin pasos educativos)",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Comprobar verificación
            if resp.verification != "Verificado matemáticamente con éxito.":
                print("SELF_TEST_FAILED: verification es None", file=sys.stderr)
                sys.exit(1)

            # Comprobar IDLE alcanzado
            if not result_holder["idle_reached"]:
                print("SELF_TEST_FAILED: estado IDLE no alcanzado", file=sys.stderr)
                sys.exit(1)

            exit_code = 0

        finally:
            # Cleanup: shutdown siempre, cerrar proceso y pipes
            try:
                ctrl.shutdown()
            except Exception:
                exit_code = 1
                print(
                    "SELF_TEST_FAILED: no se pudo cerrar el trabajador", file=sys.stderr
                )

        if exit_code == 0:
            print("SELF_TEST_OK")
        sys.exit(exit_code)

    # ------------------------------------------------------------------
    # Modo normal: lanzar la aplicación con UI completa
    # ------------------------------------------------------------------
    from src.main import main

    main()
