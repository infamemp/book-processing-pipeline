# -*- mode: python ; coding: utf-8 -*-
"""
Receta de PyInstaller para Book Pipeline.

Se usa con:   build.bat        (o: pyinstaller BookPipeline.spec --noconfirm)
Produce:      dist\\BookPipeline.exe   (un solo archivo, sin consola)

El .exe lleva dentro la ventana, el servidor local y el motor (convert.py y
extract.py). Cuando procesa un libro se llama a sí mismo con
"--motor convert|extract", así que NO necesita Python instalado.
DOCX no va incluido (MarkItDown es muy pesado); el .exe acepta EPUB y PDF.
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

RAIZ = os.path.dirname(os.path.abspath(SPEC))
ICONO = os.path.join(RAIZ, "icon.ico")
if not os.path.exists(ICONO):
    print(f"[spec] AVISO: no se encontró {ICONO}; se usa el ícono genérico")
    ICONO = None

datas = [
    (os.path.join(RAIZ, "app", "web", "index.html"), "web"),
    (os.path.join(RAIZ, "extraction_prompts.md"), "."),
]
binaries = []
hiddenimports = [
    # piezas de la app y el motor
    "config", "servidor", "trabajos", "convert", "extract",
    # ventana
    "webview", "webview.platforms.edgechromium", "webview.platforms.winforms",
    "clr_loader", "pythonnet",
]
datas += collect_data_files("webview")

# librerías del motor (se recogen completas para no fallar en tiempo de uso)
for paquete in ("google.genai", "anthropic", "pymupdf"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("markdownify") + collect_submodules("bs4") + ["fitz", "PIL.Image"]

a = Analysis(
    [os.path.join(RAIZ, "app", "ventana.py")],
    pathex=[RAIZ, os.path.join(RAIZ, "app")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "markitdown", "magika", "onnxruntime"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BookPipeline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # sin ventana negra
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICONO,
)
