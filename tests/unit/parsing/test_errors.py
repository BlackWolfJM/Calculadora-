import pytest

from src.domain.errors import StructuredMathError
from src.infrastructure.parsing.parser import MathParser


def test_unexpected_character():
    parser = MathParser()
    with pytest.raises(StructuredMathError) as exc_info:
        parser.parse("sen(&)")

    err = exc_info.value
    assert err.code == "ERR_SYNTAX_CHAR"
    assert err.line == 1
    assert err.column == 5
    assert err.fragment.startswith("&")
    assert "Carácter inesperado" in err.message


def test_unexpected_token():
    parser = MathParser()
    with pytest.raises(StructuredMathError) as exc_info:
        parser.parse("x + * 2")

    err = exc_info.value
    assert err.code == "ERR_SYNTAX_TOKEN"
    assert err.line == 1
    # 'x + * 2', '*' is at column 5
    assert err.column == 5
    assert err.fragment == "*"
    assert "Elemento inesperado" in err.message
