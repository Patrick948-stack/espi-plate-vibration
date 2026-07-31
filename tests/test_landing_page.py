"""
test_landing_page.py

Tests for the LandingPage main window.

Verifies that the landing page can be created and that button clicks work.
"""

import tempfile
from pathlib import Path
import pytest

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from espi_app.main_window import LandingPage
from espi_app.settings import SettingsManager


@pytest.fixture
def temp_config_dir(monkeypatch):
    """Create temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        monkeypatch.setattr(
            "espi_app.settings.Path.home",
            lambda: tmppath,
        )
        yield tmppath


@pytest.fixture
def qapp():
    """Create QApplication for testing."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_landing_page_initializes(qapp, temp_config_dir):
    """Test that LandingPage can be created."""
    page = LandingPage()
    assert page is not None
    assert page.windowTitle() == "ESPI Camera Control"


def test_landing_page_buttons_exist(qapp, temp_config_dir):
    """Test that all buttons exist on landing page."""
    page = LandingPage()

    # Check mode buttons
    assert page.monitor_button is not None
    assert page.scan_button is not None

    # Check control buttons
    assert page.settings_button is not None
    assert page.help_button is not None


def test_landing_page_settings_button_click(qapp, temp_config_dir):
    """Test that clicking Settings button doesn't crash."""
    page = LandingPage()

    try:
        # Simulate clicking the Settings button
        page._on_settings_clicked()
        print("✓ Settings button click succeeded")
    except Exception as e:
        pytest.fail(f"Settings button click failed: {e}")


def test_landing_page_help_button_click(qapp, temp_config_dir):
    """Test that clicking Help button doesn't crash."""
    page = LandingPage()

    try:
        # Simulate clicking the Help button
        page._on_help_clicked()
        print("✓ Help button click succeeded")
    except Exception as e:
        pytest.fail(f"Help button click failed: {e}")


def test_landing_page_monitor_button_click(qapp, temp_config_dir):
    """Test that clicking Monitor button doesn't crash."""
    page = LandingPage()

    try:
        # Simulate clicking the Monitor button
        page._on_monitor_clicked()
        print("✓ Monitor button click succeeded")
    except Exception as e:
        pytest.fail(f"Monitor button click failed: {e}")


def test_landing_page_scan_button_click(qapp, temp_config_dir):
    """Test that clicking Scan button doesn't crash."""
    page = LandingPage()

    try:
        # Simulate clicking the Scan button
        page._on_scan_clicked()
        print("✓ Scan button click succeeded")
    except Exception as e:
        pytest.fail(f"Scan button click failed: {e}")
