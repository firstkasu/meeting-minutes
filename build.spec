# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for 회의 녹음 & 정리 시스템
# 빌드: pyinstaller build.spec

import os
import sys
import site

block_cipher = None

# 사이트 패키지 경로
site_packages = site.getsitepackages()[0]

# CTranslate2, ONNX Runtime 네이티브 바이너리
binaries = []
for pkg in ["ctranslate2", "onnxruntime"]:
    pkg_dir = os.path.join(site_packages, pkg)
    if os.path.isdir(pkg_dir):
        for root, dirs, files in os.walk(pkg_dir):
            for f in files:
                if f.endswith((".dll", ".so", ".pyd")):
                    binaries.append((os.path.join(root, f), os.path.relpath(root, site_packages)))

# soundcard DLL
sc_dir = os.path.join(site_packages, "soundcard")
if os.path.isdir(sc_dir):
    for f in os.listdir(sc_dir):
        if f.endswith((".dll", ".pyd")):
            binaries.append((os.path.join(sc_dir, f), "soundcard"))

# faster-whisper medium 모델 동봉
datas = []
model_dir = os.path.join(os.path.dirname(os.path.abspath(SPECPATH)), "whisper-medium")
if os.path.isdir(model_dir):
    datas.append((model_dir, "whisper-medium"))

a = Analysis(
    ["streamlit_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        (os.path.join(site_packages, "streamlit"), "streamlit"),
        (os.path.join(site_packages, "streamlit_autorefresh"), "streamlit_autorefresh"),
    ],
    hiddenimports=[
        "soundcard",
        "soundcard.mediafoundation",
        "ctranslate2",
        "faster_whisper",
        "onnxruntime",
        "anthropic",
        "dotenv",
        "streamlit",
        "streamlit_autorefresh",
        "scipy.signal",
        "soundfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="MeetingRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MeetingRecorder",
)
