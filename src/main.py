"""
Punto de entrada principal de la Calculadora Súper Inteligente.
"""

import os
import sys

# Asegurar que el directorio raíz 'calculadoras' esté en el sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bootstrap import build_application


def main() -> None:
    print("Iniciando Calculadora Súper Inteligente (UI)...")
    app = build_application()
    print("Arquitectura y UI inicializadas correctamente.")
    sys.exit(app.exec())


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
