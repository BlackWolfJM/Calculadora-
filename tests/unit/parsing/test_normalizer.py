from src.infrastructure.parsing.normalizer import MathNormalizer


def test_normalize_empty_string():
    normalizer = MathNormalizer()
    assert normalizer.normalize("") == ""


def test_normalize_unicode_operators():
    normalizer = MathNormalizer()
    assert normalizer.normalize("2 × 3") == "2 * 3"
    assert normalizer.normalize("4 ÷ 2") == "4 / 2"
    assert normalizer.normalize("5 − 1") == "5 - 1"


def test_normalize_function_aliases():
    normalizer = MathNormalizer()
    assert normalizer.normalize("sen(x)") == "sin(x)"
    assert normalizer.normalize("tg(x)") == "tan(x)"
    assert normalizer.normalize("arcsen(x)") == "arcsin(x)"
    # Ensure it only replaces full words
    assert normalizer.normalize("sent(x)") == "sent(x)"


def test_normalize_implicit_multiplication():
    normalizer = MathNormalizer()
    # Number followed by letter
    assert normalizer.normalize("2x") == "2*x"
    # Number followed by parenthesis
    assert normalizer.normalize("3(x+1)") == "3*(x+1)"
    # Closing parenthesis followed by letter/number
    assert normalizer.normalize("(x)y") == "(x)*y"
    assert normalizer.normalize("(x)2") == "(x)*2"


def test_normalize_combination():
    normalizer = MathNormalizer()
    assert normalizer.normalize("2x sen(x) − 3(y)") == "2*x *sin(x) - 3*(y)"
