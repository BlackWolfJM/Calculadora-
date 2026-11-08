import os
import sys

# Inyectar la raíz del proyecto en sys.path para que los imports
# `from src.*` funcionen bajo pytest sin necesidad de instalar el paquete.
sys.path.insert(0, os.path.dirname(__file__))

# Asegurar flags seguras para Chromium en entornos de prueba en Windows
if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"
