"""Pruebas unitarias del subsistema de parámetros interactivos (TASK-008).

Verifica la sincronización bidireccional entre QSlider y QDoubleSpinBox,
la inversión de ciclo en animaciones y el control de rebote.
"""

from src.presentation.graphing_workspace import _ParameterRow


def test_parameter_row_bidirectional_sync(qtbot):
    """El slider y el spinbox se sincronizan bidireccionalmente sin ciclos infinitos."""
    row = _ParameterRow("a", 1.0)
    qtbot.addWidget(row)

    assert row.field.value() == 1.0
    assert row.slider.value() == 20  # 1.0 / 0.05 = 20

    emitted: list[tuple[str, float]] = []
    row.changed.connect(lambda name, val: emitted.append((name, val)))

    # Cambio desde el slider
    row.slider.setValue(40)
    assert row.field.value() == 2.0
    assert emitted[-1] == ("a", 2.0)

    # Cambio desde el spinbox
    row.field.setValue(-1.5)
    assert row.slider.value() == -30
    assert emitted[-1] == ("a", -1.5)


def test_parameter_animation_rebounce(qtbot):
    """La animación invierte el paso al alcanzar el límite superior del deslizador."""
    row = _ParameterRow("m", 4.95)
    qtbot.addWidget(row)

    assert row.slider.value() == 99
    assert row._anim_step == 1

    # Avanza al valor máximo (100)
    row._tick_animation()
    assert row.slider.value() == 100
    assert row._anim_step == -1

    # Rebote hacia abajo
    row._tick_animation()
    assert row.slider.value() == 99
    assert row._anim_step == -1


def test_parameter_animation_toggle(qtbot):
    """El botón de reproducción activa y detiene el temporizador de animación."""
    row = _ParameterRow("k", 0.0)
    qtbot.addWidget(row)

    assert not row._anim_timer.isActive()

    # Iniciar animación
    row.play_button.click()
    assert row.play_button.isChecked()
    assert row._anim_timer.isActive()
    assert row._anim_timer.interval() == 33

    # Detener animación
    row.play_button.click()
    assert not row.play_button.isChecked()
    assert not row._anim_timer.isActive()


def test_parameter_row_clamping(qtbot):
    """Valores fuera del rango [-5, 5] en el spinbox se saturan en el slider."""
    row = _ParameterRow("p", 0.0)
    qtbot.addWidget(row)

    row.field.setValue(10.0)
    assert row.slider.value() == 100
    assert row.field.value() == 10.0

    row.field.setValue(-10.0)
    assert row.slider.value() == -100
    assert row.field.value() == -10.0
