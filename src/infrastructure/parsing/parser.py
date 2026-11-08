import os
from dataclasses import fields, replace

from lark import Lark
from lark.exceptions import UnexpectedCharacters, UnexpectedToken

from src.domain.errors import StructuredMathError
from src.domain.expressions.ast_nodes import ExpressionNode, Symbol
from src.domain.expressions.source_span import SourceSpan
from src.infrastructure.parsing.ast_transformer import MathAstTransformer
from src.infrastructure.parsing.normalizer import MathNormalizer
from src.infrastructure.parsing.security import ASTSecurityValidator


class MathParser:
    def __init__(self) -> None:
        import sys

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )

        grammar_path = os.path.join(
            base_path, "src", "infrastructure", "parsing", "grammar.lark"
        )
        with open(grammar_path, "r", encoding="utf-8") as f:
            grammar_text = f.read()

        self.parser = Lark(
            grammar_text,
            parser="lalr",
            start=["start", "structured"],
            propagate_positions=True,
        )
        self.transformer = MathAstTransformer()
        self.normalizer = MathNormalizer()
        self.security = ASTSecurityValidator()

    def extract_variables(self, ast: ExpressionNode) -> set[str]:
        """Extrae recursivamente todas las variables (Symbols) de un AST."""
        variables = set()
        if isinstance(ast, Symbol):
            variables.add(ast.name)
        elif hasattr(ast, "left") and hasattr(ast, "right"):
            variables.update(self.extract_variables(ast.left))
            variables.update(self.extract_variables(ast.right))
        elif hasattr(ast, "base") and hasattr(ast, "exponent"):
            variables.update(self.extract_variables(ast.base))
            variables.update(self.extract_variables(ast.exponent))
        elif hasattr(ast, "operand"):
            variables.update(self.extract_variables(ast.operand))
        elif hasattr(ast, "arguments"):
            for arg in ast.arguments:
                variables.update(self.extract_variables(arg))
        return variables

    def parse(self, expression: str, *, structured: bool = False) -> ExpressionNode:
        """
        Analiza un string matemático y devuelve el AST seguro.
        Aplica normalización previa y límites de seguridad.
        """
        if not expression or not expression.strip():
            raise ValueError("La expresión matemática no puede estar vacía.")

        if len(expression) > 200:
            raise ValueError("La expresión supera la longitud máxima permitida.")

        normalized_expr, offsets = self.normalizer.normalize_with_map(expression)

        def original_position(index):
            return offsets[index] if index < len(offsets) else len(expression)

        def coordinates(index):
            return (
                expression.count("\n", 0, index) + 1,
                index - expression.rfind("\n", 0, index),
            )

        def remap(node):
            changes = {}
            for field in fields(node):
                value = getattr(node, field.name)
                if isinstance(value, ExpressionNode):
                    changes[field.name] = remap(value)
                elif isinstance(value, tuple):
                    changes[field.name] = tuple(remap(v) for v in value)
            if node.span:
                start = original_position(node.span.start)
                end = original_position(max(node.span.start, node.span.end - 1)) + 1
                line, column = coordinates(start)
                end_line, end_column = coordinates(end)
                changes["span"] = SourceSpan(
                    start, end, line, column, end_line, end_column
                )
            return replace(node, **changes)

        try:
            tree = self.parser.parse(
                normalized_expr, start="structured" if structured else "start"
            )
            ast = remap(self.transformer.transform(tree))
            self.security.validate(ast)
            return ast
        except UnexpectedCharacters as e:
            # Token inesperado o carácter inválido
            position = original_position(e.pos_in_stream)
            line, column = coordinates(position)
            fragment = expression[position : position + 5]
            raise StructuredMathError(
                code="ERR_SYNTAX_CHAR",
                message=f"Carácter inesperado '{fragment[0]}'",
                line=line,
                column=column,
                end_line=line,
                end_column=column + 1,
                fragment=fragment,
                suggestion="Verifica que el símbolo sea válido matemáticamente.",
                internal_cause=str(e),
            )
        except UnexpectedToken as e:
            position = original_position(e.pos_in_stream)
            line, column = coordinates(position)
            raise StructuredMathError(
                code="ERR_SYNTAX_TOKEN",
                message=f"Elemento inesperado '{e.token}'",
                line=line,
                column=column,
                end_line=line,
                end_column=column + len(str(e.token)),
                fragment=str(e.token),
                suggestion=f"Se esperaba uno de: {', '.join(e.expected)}",
                internal_cause=str(e),
            )
