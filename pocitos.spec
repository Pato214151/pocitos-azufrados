# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para Los Pocitos Azufrados POS
Genera una carpeta dist/PocitosAzufrados/ lista para distribuir.

Uso (en Windows, con PyInstaller instalado):
    pyinstaller pocitos.spec --clean

Resultado: dist/PocitosAzufrados/  ← copiar esta carpeta al cliente
"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ── Imports que PyInstaller no detecta automáticamente ──────────────────────
hiddenimports = [
    # Flask y extensiones
    'flask', 'flask.templating', 'flask.helpers', 'flask.globals',
    'flask.ctx', 'flask.signals', 'flask.wrappers',
    'jinja2', 'jinja2.ext', 'jinja2.utils',
    'werkzeug', 'werkzeug.routing', 'werkzeug.serving',
    'werkzeug.middleware.shared_data',
    'itsdangerous',
    'click',
    # Waitress (servidor de producción)
    'waitress', 'waitress.server', 'waitress.task',
    # Seguridad
    'bcrypt', 'hmac', 'hashlib', 'secrets',
    # PDF
    'reportlab', 'reportlab.pdfgen', 'reportlab.pdfgen.canvas',
    'reportlab.lib', 'reportlab.lib.pagesizes', 'reportlab.lib.units',
    'reportlab.lib.colors', 'reportlab.platypus',
    # Excel
    'openpyxl', 'openpyxl.workbook', 'openpyxl.styles',
    # Impresora ESC/POS (opcional)
    'escpos', 'escpos.printer',
    # Windows
    'win32print', 'win32api', 'win32con',
    # stdlib que a veces se pierde
    'sqlite3', 'threading', 'logging.handlers',
    'csv', 'shutil', 'subprocess',
]

# Submodules completos de algunas librerías
hiddenimports += collect_submodules('flask')
hiddenimports += collect_submodules('reportlab')
hiddenimports += collect_submodules('werkzeug')

# ── Archivos de datos a incluir ──────────────────────────────────────────────
datas = [
    # Templates y CSS de la cocina web
    ('cocina_web/templates', 'cocina_web/templates'),
    ('cocina_web/static',    'cocina_web/static'),
    # Logo del negocio
    ('logo-los-pocitos-azufrados.png', '.'),
    # Script de setup (para primer uso)
    ('setup.py', '.'),
    # Manual de usuario
    ('docs/MANUAL_USUARIO.md', '.'),
    # Datos de escpos (capabilities.json requerido al importar)
    (r'C:\Users\julianr\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\escpos\capabilities.json', 'escpos'),
]

# ── Análisis del código fuente ───────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Librerías de desarrollo/testing
        'pytest', 'unittest', '_pytest',
        # Cosas de matplotlib que no se usan en producción
        'matplotlib.tests', 'matplotlib.sphinxext',
        # No se necesita el servidor de desarrollo de Flask
        'flask.testing',
        # IPython / Jupyter
        'IPython', 'jupyter', 'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PocitosAzufrados',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # Sin ventana de consola negra
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo-los-pocitos-azufrados.ico',   # Necesita .ico (ver build_exe.bat)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PocitosAzufrados',
)
