"""Interfaz experimental del lote 1 para la calculadora existente.

La escena 2D ilustra componentes x/y; NO es una vista 3D.
"""
import math
import re

import sympy as sp
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from src.domain.modules.vector_lab import SUBTOPICS, VectorResult, calculate


_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:/[1-9]\d*)?\Z")


def _parse_vector(text: str) -> list[sp.Rational]:
    parts = [item.strip() for item in text.split(",")]
    if len(parts) not in (2, 3):
        raise ValueError("Introduce 2 o 3 coordenadas separadas por comas.")
    if any(len(x) > 40 or not _NUMBER.fullmatch(x) for x in parts):
        raise ValueError("Usa números racionales: por ejemplo 3, -2 o 1/2.")
    return [sp.Rational(x) for x in parts]


class VectorLabWidget(QWidget):
    """Panel embebido sin otra ventana ni otra calculadora."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Laboratorio de vectores · Lote 1")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        self.topic = QComboBox()
        for key, label in SUBTOPICS.items():
            self.topic.addItem(f"{key} · {label}", key)
        self.topic.setAccessibleName("Subtema del laboratorio")
        form = QFormLayout()
        form.addRow("Subtema", self.topic)
        self.a = QLineEdit("3, 2")
        self.b = QLineEdit("-1, 4")
        self.a.setAccessibleName("Vector u o punto A")
        self.b.setAccessibleName("Vector v o punto B")
        form.addRow("Vector u / punto A", self.a)
        form.addRow("Vector v / punto B", self.b)
        self.operation = QComboBox()
        self.operation.addItem("Suma", "sum")
        self.operation.addItem("Resta", "difference")
        form.addRow("Operación 01.07", self.operation)
        self.k = QSlider(Qt.Orientation.Horizontal)
        self.k.setRange(-50, 50)
        self.k.setValue(20)
        self.k.setAccessibleName("Factor escalar k")
        self.scalar_text = QLabel("k = 2.0")
        slider_row = QHBoxLayout()
        slider_row.addWidget(self.k)
        slider_row.addWidget(self.scalar_text)
        slider_box = QWidget()
        slider_box.setLayout(slider_row)
        form.addRow("Factor escalar", slider_box)
        layout.addLayout(form)

        self.solve = QPushButton("Calcular y visualizar")
        self.solve.setAccessibleName("Resolver subtema")
        layout.addWidget(self.solve)
        self.answer = QLabel()
        self.answer.setWordWrap(True)
        self.answer.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.answer)
        self.scene = QGraphicsScene(self)
        self.canvas = QGraphicsView(self.scene)
        self.canvas.setMinimumHeight(270)
        self.canvas.setAccessibleName("Proyección cartesiana de los vectores")
        layout.addWidget(self.canvas)
        warning = QLabel(
            "Vista de los componentes x/y. Para vectores 3D esta es una "
            "proyección 2D, no una representación espacial completa."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addWidget(QLabel("Procedimiento (expande cada paso):"))
        self.steps = QTreeWidget()
        self.steps.setHeaderHidden(True)
        self.steps.setMinimumHeight(150)
        layout.addWidget(self.steps)
        layout.addStretch()

        self.topic.currentIndexChanged.connect(self._refresh_options)
        self.k.valueChanged.connect(self._slider_changed)
        self.solve.clicked.connect(self.recalculate)
        self.a.returnPressed.connect(self.recalculate)
        self.b.returnPressed.connect(self.recalculate)
        self._refresh_options()
        self.recalculate()

    def _slider_changed(self, value: int) -> None:
        self.scalar_text.setText(f"k = {value / 10:g}")
        self.recalculate()

    def _refresh_options(self) -> None:
        item = self.topic.currentData()
        self.operation.setVisible(item == "01.07")
        self.operation.setEnabled(item == "01.07")
        self.k.setEnabled(item in ("01.08", "01.09", "01.10"))
        self.recalculate()

    def recalculate(self) -> None:
        try:
            a = _parse_vector(self.a.text())
            b = _parse_vector(self.b.text())
            result = calculate(
                str(self.topic.currentData()), a, b,
                sp.Rational(self.k.value(), 10),
                str(self.operation.currentData()),
            )
            self.answer.setText(
                f"{result.title}\nResultado: {result.value}\n{result.note}"
            )
            self.answer.setStyleSheet("font-weight: 600;")
            self._draw(result)
            self.steps.clear()
            for step in result.steps:
                node = QTreeWidgetItem([step.rule_name])
                node.addChild(QTreeWidgetItem([step.explanation]))
                node.addChild(QTreeWidgetItem(
                    [f"{step.before_latex}  ⇒  {step.after_latex}"]
                ))
                self.steps.addTopLevelItem(node)
            self.steps.expandAll()
        except (ValueError, TypeError, OverflowError, ArithmeticError) as exc:
            self.answer.setText(f"No se puede resolver: {exc}")
            self.answer.setStyleSheet("color: #b33b35;")
            self.steps.clear()
            self.scene.clear()

    def _draw(self, result: VectorResult) -> None:
        self.scene.clear()
        arrows = result.arrows
        coords = [p for _, a, b in arrows for p in (a, b)]
        extent = max([1.0] + [abs(c) for xy in coords for c in xy])
        if not math.isfinite(extent):
            raise ValueError("Coordenadas fuera del rango gráfico.")
        scale = 110 / extent
        pen_axis = QPen(QColor("#7d8794"))
        self.scene.addLine(-160, 0, 160, 0, pen_axis)
        self.scene.addLine(0, -160, 0, 160, pen_axis)
        self.scene.addText("x").setPos(145, 1)
        self.scene.addText("y").setPos(4, -160)
        palette = ("#2563eb", "#dc6d2b", "#16a085", "#7e57c2")
        for index, (label, start, end) in enumerate(arrows):
            color = QColor(palette[index % len(palette)])
            pen = QPen(color)
            pen.setWidth(3)
            x1, y1 = start[0] * scale, -start[1] * scale
            x2, y2 = end[0] * scale, -end[1] * scale
            self.scene.addLine(x1, y1, x2, y2, pen)
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length > 0.01:
                ux, uy = dx / length, dy / length
                p1 = QPointF(x2 - 10 * ux - 5 * uy, y2 - 10 * uy + 5 * ux)
                p2 = QPointF(x2 - 10 * ux + 5 * uy, y2 - 10 * uy - 5 * ux)
                self.scene.addPolygon(
                    QPolygonF([QPointF(x2, y2), p1, p2]),
                    pen, QBrush(color)
                )
            text = self.scene.addText(label)
            text.setDefaultTextColor(color)
            text.setPos(x2 + 4, y2 - 22)
        self.scene.setSceneRect(-185, -175, 370, 350)
        self.canvas.fitInView(
            self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )
