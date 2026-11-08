from typing import Optional

from src.domain.modules.protocol import MathModule


class ModuleRegistry:
    """
    Registro centralizado para todos los módulos matemáticos soportados.
    Permite obtener un módulo a partir de su ID.
    """

    def __init__(self):
        self._modules: dict[str, MathModule] = {}

    def register(self, module: MathModule) -> None:
        """Registra un módulo en el sistema. Lanza ValueError si hay colisión de IDs."""
        module_id = module.get_id()
        if module_id in self._modules:
            raise ValueError(f"Ya existe un módulo registrado con el id: {module_id}")
        self._modules[module_id] = module

    def get_module(self, module_id: str) -> Optional[MathModule]:
        """Obtiene un módulo por su ID, o None si no se encuentra."""
        return self._modules.get(module_id)

    def get_all_modules(self) -> list[MathModule]:
        """Devuelve todos los módulos registrados."""
        return list(self._modules.values())
