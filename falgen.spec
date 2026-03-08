# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for falgen — single-file binary."""

import os
import importlib

block_cipher = None

# Locate textual package for data files
textual_pkg = importlib.import_module("textual")
textual_dir = os.path.dirname(textual_pkg.__file__)

# Skill markdown files
skills_dir = os.path.join("src", "falgen", "skills")
skill_files = [(os.path.join(skills_dir, f), "skills") for f in os.listdir(skills_dir) if f.endswith(".md")]

a = Analysis(
    ["src/falgen/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=skill_files + [
        (os.path.join(textual_dir, "css"), os.path.join("textual", "css")),
    ],
    hiddenimports=[
        "falgen",
        "falgen.app",
        "falgen.auth",
        "falgen.config",
        "falgen.preferences",
        "falgen.session",
        "falgen.widgets",
        "falgen.commands",
        "falgen.commands.base",
        "falgen.commands.builtins",
        "falgen.commands.cli_commands",
        "falgen.providers",
        "falgen.providers.openrouter",
        "falgen.tools",
        "falgen.tools.base",
        "falgen.tools.ask_user",
        "falgen.tools.generate",
        "falgen.tools.search",
        "falgen.tools.info",
        "falgen.tools.history",
        "falgen.tools.pricing",
        "falgen.tools.usage",
        "falgen.tools.workflows",
        "falgen.tools.skills",
        "falgen.skills",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="falgen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
