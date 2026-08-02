"""
test_settings_dialog_legacy.py

Tests for the SettingsDialog class. Renamed from test_settings_dialog.py
(kept its content unchanged) since ESPI Full Algorithm/tests/ has its own,
unrelated test_settings_dialog.py testing a different SettingsPage class --
the shared basename across two separate test directories with no
__init__.py in either caused a pytest collection error when running
pytest from the project root.

Verifies that the settings dialog can:
- Load current settings
- Display them in the UI
- Save changes back to the SettingsManager
- Handle camera choice selection correctly
"""

import json
import tempfile
from pathlib import Path
import pytest

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from espi_app.settings import SettingsManager
from espi_app.settings_dialog import SettingsDialog, CAMERA_NAMES


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


def test_camera_names_defined():
    """Test that CAMERA_NAMES dictionary is correctly defined."""
    assert "1" in CAMERA_NAMES
    assert "2" in CAMERA_NAMES
    assert "3" in CAMERA_NAMES
    assert CAMERA_NAMES["1"] == "Basler"
    assert CAMERA_NAMES["2"] == "USB / webcam (eg. elp camera)"
    assert CAMERA_NAMES["3"] == "Allied Vision"


def test_settings_dialog_initializes(qapp, temp_config_dir):
    """Test that SettingsDialog can be created and initialized."""
    dialog = SettingsDialog()

    # Check that dialog was created
    assert dialog is not None
    assert dialog.windowTitle() == "Settings"

    # Check that tabs exist
    assert dialog.tabs is not None
    assert dialog.tabs.count() == 3  # Hardware, Visualization, UI


def test_settings_dialog_loads_defaults(qapp, temp_config_dir):
    """Test that dialog loads default settings on first run."""
    mgr = SettingsManager()
    dialog = SettingsDialog()

    # Camera should default to Basler ("1")
    camera_choice = dialog.camera_combo.currentData()
    assert camera_choice == "1"

    # Exposure should be default
    assert dialog.exposure_spin.value() == 5.0

    # Theme should be default
    assert dialog.theme_combo.currentText().lower() == "light"


def test_settings_dialog_camera_combo_has_all_options(qapp, temp_config_dir):
    """Test that camera combo has all three camera options."""
    dialog = SettingsDialog()

    # Check that all three cameras are in the combo
    assert dialog.camera_combo.count() == 3

    # Check the order and data
    for i, (choice_code, camera_name) in enumerate(CAMERA_NAMES.items()):
        # Get the item at position i
        text = dialog.camera_combo.itemText(i)
        data = dialog.camera_combo.itemData(i)

        # Verify text matches camera name
        assert text == camera_name
        # Verify data matches choice code
        assert data == choice_code


def test_settings_dialog_saves_camera_choice(qapp, temp_config_dir):
    """Test that dialog saves the selected camera choice."""
    dialog = SettingsDialog()

    # Change camera to "3" (Allied Vision)
    index = dialog.camera_combo.findData("3")
    assert index >= 0  # Should find the option
    dialog.camera_combo.setCurrentIndex(index)

    # Simulate clicking Save
    dialog._on_save()

    # Create new manager to verify it was saved
    mgr = SettingsManager()
    saved_choice = mgr.get("hardware.default_camera_choice")
    assert saved_choice == "3"


def test_settings_dialog_saves_exposure(qapp, temp_config_dir):
    """Test that dialog saves exposure setting."""
    dialog = SettingsDialog()

    # Change exposure
    dialog.exposure_spin.setValue(15.0)

    # Save
    dialog._on_save()

    # Verify it was saved
    mgr = SettingsManager()
    assert mgr.get("hardware.exposure_ms") == 15.0


def test_settings_dialog_saves_visualization_settings(qapp, temp_config_dir):
    """Test that dialog saves visualization checkboxes."""
    dialog = SettingsDialog()

    # Uncheck histogram
    dialog.show_histogram_check.setChecked(False)
    dialog.show_intensity_check.setChecked(False)

    # Save
    dialog._on_save()

    # Verify
    mgr = SettingsManager()
    assert mgr.get("visualization.show_histogram") is False
    assert mgr.get("visualization.show_intensity_graph") is False


def test_settings_dialog_saves_theme(qapp, temp_config_dir):
    """Test that dialog saves theme selection."""
    dialog = SettingsDialog()

    # Change theme to Dark
    index = dialog.theme_combo.findText("Dark")
    dialog.theme_combo.setCurrentIndex(index)

    # Save
    dialog._on_save()

    # Verify
    mgr = SettingsManager()
    assert mgr.get("ui.theme") == "dark"


def test_settings_dialog_cancel_doesnt_save(qapp, temp_config_dir):
    """Test that clicking Cancel doesn't save changes."""
    # Set initial value
    mgr = SettingsManager()
    mgr.set("hardware.exposure_ms", 5.0)
    mgr.save()

    dialog = SettingsDialog()

    # Change exposure
    dialog.exposure_spin.setValue(999.0)

    # Click Cancel (calls reject())
    dialog.reject()

    # Verify it wasn't saved
    mgr2 = SettingsManager()
    assert mgr2.get("hardware.exposure_ms") == 5.0
    assert mgr2.get("hardware.exposure_ms") != 999.0


def test_settings_dialog_loads_saved_values(qapp, temp_config_dir):
    """Test that dialog loads previously saved values."""
    # Save some custom settings
    mgr = SettingsManager()
    mgr.set("hardware.default_camera_choice", "2")
    mgr.set("hardware.exposure_ms", 20.0)
    mgr.set("visualization.show_histogram", False)
    mgr.save()

    # Create new dialog
    dialog = SettingsDialog()

    # Verify it loaded the saved values
    assert dialog.camera_combo.currentData() == "2"
    assert dialog.exposure_spin.value() == 20.0
    assert dialog.show_histogram_check.isChecked() is False


def test_settings_manager_has_camera_choice_field(temp_config_dir):
    """Test that SettingsManager has the camera_choice field."""
    mgr = SettingsManager()

    # Should have default_camera_choice
    camera_choice = mgr.get("hardware.default_camera_choice")
    assert camera_choice in ["1", "2", "3"]


def test_settings_json_structure_valid(temp_config_dir):
    """Test that saved settings.json has valid structure."""
    mgr = SettingsManager()
    mgr.set("hardware.default_camera_choice", "1")
    mgr.save()

    # Read the JSON file directly
    with open(mgr.config_file, "r") as f:
        data = json.load(f)

    # Verify structure
    assert "hardware" in data
    assert "default_camera_choice" in data["hardware"]
    assert data["hardware"]["default_camera_choice"] == "1"


def test_settings_dialog_has_remember_checkbox(qapp, temp_config_dir):
    """Test that the 'Remember Last Settings' checkbox exists."""
    dialog = SettingsDialog()

    # Check that the checkbox exists
    assert hasattr(dialog, "remember_last_settings_check")
    assert dialog.remember_last_settings_check is not None


def test_settings_dialog_saves_remember_setting(qapp, temp_config_dir):
    """Test that the 'Remember Last Settings' checkbox value is saved."""
    dialog = SettingsDialog()

    # Uncheck "Remember Last Settings"
    dialog.remember_last_settings_check.setChecked(False)

    # Save
    dialog._on_save()

    # Verify it was saved
    mgr = SettingsManager()
    assert mgr.get("persistence.remember_last_settings") is False


def test_settings_dialog_saves_last_used_values(qapp, temp_config_dir):
    """Test that last_used values are saved when remember is enabled."""
    dialog = SettingsDialog()

    # Ensure "Remember Last Settings" is checked
    dialog.remember_last_settings_check.setChecked(True)

    # Change camera and exposure
    index = dialog.camera_combo.findData("3")
    dialog.camera_combo.setCurrentIndex(index)
    dialog.exposure_spin.setValue(25.0)

    # Save
    dialog._on_save()

    # Verify last_used values were saved
    mgr = SettingsManager()
    assert mgr.get("persistence.last_used_camera_choice") == "3"
    assert mgr.get("persistence.last_used_exposure") == 25.0


def test_settings_manager_loads_last_used_values(temp_config_dir):
    """Test that SettingsManager can load last_used values."""
    mgr = SettingsManager()

    # Set and save last_used values
    mgr.set("persistence.last_used_camera_choice", "2")
    mgr.set("persistence.last_used_exposure", 30.0)
    mgr.save()

    # Load in new manager
    mgr2 = SettingsManager()

    # Verify last_used values are loaded
    assert mgr2.get("persistence.last_used_camera_choice") == "2"
    assert mgr2.get("persistence.last_used_exposure") == 30.0


def test_settings_dialog_has_gain_checkboxes(qapp, temp_config_dir):
    """Test that gain control checkboxes exist in hardware tab."""
    dialog = SettingsDialog()

    # Check that checkboxes exist
    assert hasattr(dialog, "control_gain_check")
    assert hasattr(dialog, "control_gain_factor_check")
    assert dialog.control_gain_check is not None
    assert dialog.control_gain_factor_check is not None


def test_settings_dialog_loads_gain_defaults(qapp, temp_config_dir):
    """Test that gain checkboxes load default values."""
    dialog = SettingsDialog()

    # Gain controls should default to False
    assert dialog.control_gain_check.isChecked() is False
    assert dialog.control_gain_factor_check.isChecked() is False


def test_settings_dialog_saves_gain_settings(qapp, temp_config_dir):
    """Test that gain checkbox values are saved."""
    dialog = SettingsDialog()

    # Enable both gain controls
    dialog.control_gain_check.setChecked(True)
    dialog.control_gain_factor_check.setChecked(True)

    # Save
    dialog._on_save()

    # Verify they were saved
    mgr = SettingsManager()
    assert mgr.get("hardware.control_gain") is True
    assert mgr.get("hardware.control_gain_factor") is True


def test_settings_dialog_loads_saved_gain_settings(qapp, temp_config_dir):
    """Test that dialog loads previously saved gain settings."""
    # Save some custom gain settings
    mgr = SettingsManager()
    mgr.set("hardware.control_gain", True)
    mgr.set("hardware.control_gain_factor", False)
    mgr.save()

    # Create new dialog
    dialog = SettingsDialog()

    # Verify it loaded the saved values
    assert dialog.control_gain_check.isChecked() is True
    assert dialog.control_gain_factor_check.isChecked() is False


def test_settings_dialog_emits_theme_changed_signal(qapp, temp_config_dir):
    """Test that theme_changed signal is emitted when theme changes."""
    dialog = SettingsDialog()

    # Track signal emissions
    signal_emitted = []
    dialog.theme_changed.connect(lambda theme: signal_emitted.append(theme))

    # Change theme from light to dark
    index = dialog.theme_combo.findText("Dark")
    dialog.theme_combo.setCurrentIndex(index)

    # Save
    dialog._on_save()

    # Verify signal was emitted with "dark"
    assert len(signal_emitted) == 1
    assert signal_emitted[0] == "dark"


def test_settings_dialog_no_signal_if_theme_unchanged(qapp, temp_config_dir):
    """Test that theme_changed signal is NOT emitted if theme doesn't change."""
    dialog = SettingsDialog()

    # Track signal emissions
    signal_emitted = []
    dialog.theme_changed.connect(lambda theme: signal_emitted.append(theme))

    # Don't change theme, just save
    dialog._on_save()

    # Verify signal was NOT emitted
    assert len(signal_emitted) == 0
