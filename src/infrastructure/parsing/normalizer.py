import re


class MathNormalizer:
    """Token-aware normalization with original-character offsets."""

    aliases = {"sen": "sin", "tg": "tan", "arcsen": "arcsin"}
    functions = {
        "sin",
        "cos",
        "tan",
        "ln",
        "log10",
        "sqrt",
        "abs",
        "exp",
        "arcsin",
        "arccos",
        "arctan",
    }
    token = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z]+\d*|\s+|.")

    def normalize(self, expression: str) -> str:
        return self.normalize_with_map(expression)[0]

    def normalize_with_map(self, expression: str) -> tuple[str, list[int]]:
        output, offsets = [], []
        previous = ""
        replacements = {"×": "*", "÷": "/", "−": "-"}
        for match in self.token.finditer(expression):
            raw = match.group()
            if raw.isspace():
                output.append(" ")
                offsets.append(match.start())
                continue
            value = self.aliases.get(raw, replacements.get(raw, raw))
            ends_atom = (
                previous == ")"
                or previous[:1].isdigit()
                or (previous.isalpha() and len(previous) == 1)
            )
            starts_atom = value == "(" or value[:1].isdigit() or value[:1].isalpha()
            function_call = previous in self.functions and value == "("
            if ends_atom and starts_atom and not function_call:
                output.append("*")
                offsets.append(match.start())
            output.append(value)
            offsets.extend(
                match.start() + min(i, len(raw) - 1) for i in range(len(value))
            )
            previous = value
        return "".join(output), offsets
