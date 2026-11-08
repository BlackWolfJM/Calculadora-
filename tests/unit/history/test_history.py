import datetime
import uuid

import pytest

from src.domain.history import HistoryEntry
from src.infrastructure.sqlite_history import SQLiteHistoryRepository


@pytest.fixture
def repo():
    # Usamos una base de datos en memoria compartida, pero con un ID
    # único por cada prueba para que no se filtren datos entre tests.
    db_name = f"test_memdb_{uuid.uuid4().hex}"
    return SQLiteHistoryRepository(f"file:{db_name}?mode=memory&cache=shared")


def test_save_and_retrieve_history(repo):
    entry1 = HistoryEntry(
        id="h_001",
        original_input="x^2",
        module_id="derivatives",
        created_at=datetime.datetime(2025, 1, 1, 12, 0),
        response_summary="2*x",
    )

    entry2 = HistoryEntry(
        id="h_002",
        original_input="sin(x)",
        module_id="derivatives",
        created_at=datetime.datetime(2025, 1, 1, 12, 5),
        response_summary="cos(x)",
    )

    repo.save(entry1)
    repo.save(entry2)

    # Debe devolver ordenado por fecha descendente
    results = repo.get_all()
    assert len(results) == 2
    assert results[0].id == "h_002"
    assert results[1].id == "h_001"


def test_clear_history(repo):
    entry = HistoryEntry(
        id="h_003",
        original_input="e^x",
        module_id="derivatives",
        created_at=datetime.datetime.now(),
        response_summary="e^x",
    )

    repo.save(entry)
    assert len(repo.get_all()) == 1

    repo.clear()
    assert len(repo.get_all()) == 0
