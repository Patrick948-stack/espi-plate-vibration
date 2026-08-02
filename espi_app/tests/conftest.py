"""
conftest.py — shared pytest fixtures for espi_app GUI tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_home(tmp_path, monkeypatch):
    """
    SettingsManager reads and writes ~/.espi_app/settings.json (see
    espi_app/settings.py). Redirecting Path.home() to a per-test tmp_path
    means every test starts from factory defaults and never touches, or
    overwrites, the real user's saved settings.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
