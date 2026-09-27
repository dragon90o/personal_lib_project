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
    datas=collect_data_files('piper'),
    hiddenimports=['piper.espeakbridge'],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ReadAloud',
    # with a console window: it shows the voice downloads and the address,
    # and closing it is how the reader is stopped
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name='ReadAloud')
