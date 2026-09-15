# -*- coding: utf-8 -*-
"""Все скрипты агента синтаксически корректны."""
import py_compile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", sorted(str(p) for p in list((ROOT / "interview").glob("*.py")) + list((ROOT / "lesson").glob("*.py"))))
def test_compiles(path):
    py_compile.compile(path, doraise=True)
