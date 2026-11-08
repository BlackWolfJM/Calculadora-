"""
Test de empaquetado: construye un .exe con PyInstaller y ejecuta --self-test.

Usa console=True en la build de test para poder capturar stdout.
"""

import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.slow
def test_self_test_cli_isolated(tmp_path):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    run_script = os.path.join(project_root, "run.py")
    grammar_file = os.path.join(
        project_root, "src", "infrastructure", "parsing", "grammar.lark"
    )
    assets_dir = os.path.join(project_root, "src", "presentation", "assets")

    # Crear un .spec de prueba con console=True para capturar stdout
    spec_content = textwrap.dedent(f"""\
        # -*- mode: python ; coding: utf-8 -*-
        a = Analysis(
            [{run_script!r}],
            pathex=[{project_root!r}],
            binaries=[],
            datas=[
                ({assets_dir!r}, 'src/presentation/assets'),
                ({grammar_file!r}, 'src/infrastructure/parsing'),
            ],
            hiddenimports=[],
            hookspath=[],
            hooksconfig={{}},
            runtime_hooks=[],
            excludes=[],
            noarchive=False,
            optimize=0,
        )
        # La aplicación usa Qt Widgets/WebEngine, no componentes QML.
        a.datas = [item for item in a.datas
                   if not item[0].replace('\\\\', '/').startswith('PySide6/qml/')]
        a.binaries = [item for item in a.binaries
                      if not item[0].replace('\\\\', '/').startswith('PySide6/qml/')]
        pyz = PYZ(a.pure)
        exe = EXE(
            pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name='CalculadoraSuperInteligente_Test',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=False,
            console=True,
            disable_windowed_traceback=False,
            argv_emulation=False,
        )
        coll = COLLECT(
            exe,
            a.binaries,
            a.datas,
            strip=False,
            upx=False,
            upx_exclude=[],
            name='CalculadoraSuperInteligente_Test',
        )
    """)

    spec_file = tmp_path / "test_build.spec"
    spec_file.write_text(spec_content, encoding="utf-8")

    # Construir con PyInstaller
    build_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec_file),
            "--distpath",
            str(tmp_path / "dist"),
            "--workpath",
            str(tmp_path / "build"),
            "--noconfirm",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=300,
    )

    assert build_result.returncode == 0, (
        f"PyInstaller falló (exit {build_result.returncode}):\n"
        f"stdout: {build_result.stdout[-2000:]}\n"
        f"stderr: {build_result.stderr[-2000:]}"
    )

    # Localizar el ejecutable
    exe_path = (
        tmp_path
        / "dist"
        / "CalculadoraSuperInteligente_Test"
        / "CalculadoraSuperInteligente_Test.exe"
    )
    assert exe_path.exists(), f"Ejecutable no encontrado en {exe_path}"

    # Ejecutar --self-test desde un directorio temporal limpio
    test_cwd = tmp_path / "run_dir"
    test_cwd.mkdir()

    run_result = subprocess.run(
        [str(exe_path), "--self-test"],
        capture_output=True,
        text=True,
        cwd=str(test_cwd),
        timeout=30,
    )

    assert run_result.returncode == 0, (
        f"--self-test falló (exit {run_result.returncode}):\n"
        f"stdout: {run_result.stdout[-2000:]}\n"
        f"stderr: {run_result.stderr[-2000:]}"
    )
    assert "SELF_TEST_OK" in run_result.stdout

    # Verificar que no se creó la base de datos SQLite en el cwd de test
    db_path = test_cwd / "calculadora_history.db"
    assert not db_path.exists(), (
        f"calculadora_history.db se creó en {test_cwd} durante --self-test"
    )
