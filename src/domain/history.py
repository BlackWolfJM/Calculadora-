import datetime
from dataclasses import dataclass, field
from typing import List, Protocol


@dataclass
class HistoryEntry:
    id: str
    original_input: str
    module_id: str
    created_at: datetime.datetime
    # Por el momento la persistencia guarda un extracto o la respuesta JSON
    # para no acoplar el esquema SQL a todos los campos matemáticos.
    response_summary: str
    parameters: dict = field(default_factory=dict)


class HistoryRepository(Protocol):
    """
    Contrato para persistir y recuperar el historial local.
    """

    def save(self, entry: HistoryEntry) -> None: ...

    def get_all(self, limit: int = 50) -> List[HistoryEntry]: ...

    def clear(self) -> None: ...

    def close(self) -> None: ...
