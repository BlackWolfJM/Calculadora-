import sympy

from src.infrastructure.parsing.parser import MathParser
from src.infrastructure.sympy_adapter import SympyAdapter


def convert(text: str):
    parser = MathParser()
    adapter = SympyAdapter()
    return adapter.ast_to_sympy(parser.parse(text))


def test_abs_mapping():
    x = sympy.Symbol("x", real=True)
    assert convert("abs(x)") == sympy.Abs(x)


def test_arcsin_alias_mapping():
    x = sympy.Symbol("x", real=True)
    assert convert("arcsen(x)") == sympy.asin(x)


def test_arccos_mapping():
    x = sympy.Symbol("x", real=True)
    assert convert("arccos(x)") == sympy.acos(x)


def test_arctan_mapping():
    x = sympy.Symbol("x", real=True)
    assert convert("arctan(x)") == sympy.atan(x)


def test_log10_mapping():
    x = sympy.Symbol("x", real=True)
    assert convert("log10(x)") == sympy.log(x, 10)
