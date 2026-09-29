# -*- mode: python ; coding: utf-8 -*-
# Builds ReadAloud.exe: the reader packaged with its own Python, for people who
# have never installed one. From the project folder, in the venv:
#
#     pip install pyinstaller
#     pyinstaller readaloud.spec
#
# The result is dist/ReadAloud/ (a folder, not a single exe: it starts much
# faster, since nothing has to be unpacked on every launch). Zip that folder
# to publish it. The voices are not bundled: server.py downloads each one the
# first time a book in its language needs it, into %LOCALAPPDATA%\ReadAloud.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ['server.py'],
    # Piper's data (the espeak-ng pronunciation rules) and its compiled
    # espeakbridge are not found by following the imports alone
    binaries=collect_dynamic_libs('piper'),
    # the icon goes along too: the tray and the browser tab use the png.
    # RapidOCR's models and config.yaml (orientation.py) are data files too
    datas=collect_data_files('piper') + collect_data_files('rapidocr_onnxruntime')
    + [('assets/readaloud.png', 'assets')],
    # pystray picks its backend at run time, so the Windows one is not found
    # by following the imports
    hiddenimports=['piper.espeakbridge', 'pystray._win32'],
    # the personal translation add-on never goes into the published program,
    # even when built from a folder that has translate.py
    excludes=['translate'],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ReadAloud',
    icon='assets/readaloud.ico',
    # no console window: a black window full of text made it look like a
    # virus. The program lives in the tray instead (Open library / Quit),
    # what used to be printed goes to readaloud.log in the data folder, and
    # the voice downloads show up in the pages themselves
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='ReadAloud')
