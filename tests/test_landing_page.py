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


def test_landing_page_initializes(qapp, temp_config_dir, qtbot):
    """Test that LandingPage can be created."""
    page = LandingPage()
    qtbot.addWidget(page)
    assert page is not None
    assert page.windowTitle() == "ESPI Camera Control"


def test_landing_page_buttons_exist(qapp, temp_config_dir, qtbot):
    """Test that all buttons exist on landing page."""
    page = LandingPage()
    qtbot.addWidget(page)

    # Check mode buttons
    assert page.monitor_button is not None
    assert page.scan_button is not None

    # Check control buttons
    assert page.settings_button is not None
    assert page.help_button is not None


def test_landing_page_settings_button_click(qapp, temp_config_dir, qtbot, monkeypatch):
    """Test that clicking Settings button doesn't crash.

    SettingsDialog.exec() opens a real modal dialog. Under a headless
    (offscreen) Qt platform there is no user to close it, so a real
    exec() call blocks forever. Patch it to behave like a dialog the
    user immediately closed, matching how modal calls are mocked
    elsewhere in this project (see ESPI Full Algorithm/tests/test_monitor_gui.py).
    """
    from espi_app.settings_dialog import SettingsDialog

    monkeypatch.setattr(SettingsDialog, "exec", lambda self: None)

    page = LandingPage()
    qtbot.addWidget(page)

    try:
        # Simulate clicking the Settings button
        page._on_settings_clicked()
        print("✓ Settings button click succeeded")
    except Exception as e:
        pytest.fail(f"Settings button click failed: {e}")


def test_landing_page_help_button_click(qapp, temp_config_dir, qtbot, monkeypatch):
    """Test that clicking Help button doesn't crash.

    QMessageBox.information() is a real modal call and blocks forever
    under a headless Qt platform for the same reason as dialog.exec()
    above. Patch it so the click handler runs to completion.
    """
    monkeypatch.setattr(
        "espi_app.main_window.QMessageBox.information", lambda *args, **kwargs: None
    )

    page = LandingPage()
    qtbot.addWidget(page)

    try:
        # Simulate clicking the Help button
        page._on_help_clicked()
        print("✓ Help button click succeeded")
    except Exception as e:
        pytest.fail(f"Help button click failed: {e}")


def test_landing_page_monitor_button_click(qapp, temp_config_dir, qtbot, monkeypatch):
    """Test that clicking Monitor button doesn't crash.

    _on_monitor_clicked() builds the real Monitor dashboard window,
    which imports matplotlib. LandingPage's own job here is just to
    verify it wires the click through to a window and disables the
    button while it's open; the dashboard's own construction is
    already covered by ESPI Full Algorithm/tests/test_monitor_gui.py.
    Stub the window factory so this test stays fast and does not
    depend on matplotlib being importable in this environment.

    The stub is registered with qtbot (not just returned bare) so its
    C++ side is torn down deterministically at the end of this test
    instead of being left for Python's garbage collector to clean up
    in whatever order it likes, which is what caused segfaults here
    when this file's tests ran back to back.
    """
    from PyQt6.QtWidgets import QWidget

    def fake_create_monitor_window(self):
        stub = QWidget()
        qtbot.addWidget(stub)
        return stub

    monkeypatch.setattr(LandingPage, "_create_monitor_window", fake_create_monitor_window)

    page = LandingPage()
    qtbot.addWidget(page)

    try:
        # Simulate clicking the Monitor button
        page._on_monitor_clicked()
        print("✓ Monitor button click succeeded")
    except Exception as e:
        pytest.fail(f"Monitor button click failed: {e}")


def test_landing_page_scan_button_click(qapp, temp_config_dir, qtbot, monkeypatch):
    """Test that clicking Scan button doesn't crash.

    Same reasoning as test_landing_page_monitor_button_click above:
    stub the window factory instead of building the real Scan
    dashboard (which also imports matplotlib), and let qtbot own the
    stub's lifecycle.
    """
    from PyQt6.QtWidgets import QWidget

    def fake_create_scan_window(self):
        stub = QWidget()
        qtbot.addWidget(stub)
        return stub

    monkeypatch.setattr(LandingPage, "_create_scan_window", fake_create_scan_window)

    page = LandingPage()
    qtbot.addWidget(page)

    try:
        # Simulate clicking the Scan button
        page._on_scan_clicked()
        print("✓ Scan button click succeeded")
    except Exception as e:
        pytest.fail(f"Scan button click failed: {e}")
