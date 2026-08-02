"""
test_settings_dialog.py
Tests for espi_app/settings_dialog.py (SettingsDialog).

Covers the settings added on top of the original dialog: preview window
size, auto-rescale graphs, remember window geometry, and show tooltips.
Confirms each one loads its saved value on open and writes it back to
disk on Save.
"""

import pytest

from espi_app.main_window import _ensure_espi_algorithm_on_path
from espi_app.settings import SettingsManager
from espi_app.settings_dialog import SettingsDialog


def _espi_full_algorithm_settings_manager():
    """Import ESPI Full Algorithm's settings_manager, bridging sys.path first."""
    _ensure_espi_algorithm_on_path()
    import settings_manager

    return settings_manager


class TestNewSettingsLoadDefaults:
    def test_hardware_tab_loads_default_preview_size(self, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.preview_size_combo.currentText() == "Medium"

    def test_ui_tab_loads_default_geometry_and_tooltip_checkboxes(self, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.remember_geometry_check.isChecked() is True
        assert dialog.show_tooltips_check.isChecked() is True


class TestNewSettingsSaveToDisk:
    def test_save_writes_every_new_control_to_disk(self, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        dialog.preview_size_combo.setCurrentText("Large")
        dialog.remember_geometry_check.setChecked(False)
        dialog.show_tooltips_check.setChecked(False)

        dialog._on_save()

        on_disk = SettingsManager()
        assert on_disk.get("hardware.preview_size") == "Large"
        assert on_disk.get("ui.remember_window_geometry") is False
        assert on_disk.get("ui.show_tooltips") is False


class TestRemovedSettings:
    def test_max_framerate_and_graph_update_ms_are_gone(self, qtbot):
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, "framerate_combo")
        assert not hasattr(dialog, "graph_update_slider")
        assert not hasattr(dialog, "graph_update_label")

    def test_visualization_tab_is_gone(self, qtbot):
        """
        The Visualization tab (which graphs to show) was removed entirely:
        it duplicated monitor_gui.py's own graph_type picker with no way
        for espi_app to actually apply the choice to either dashboard.
        """
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert not hasattr(dialog, "visualization_tab")
        assert not hasattr(dialog, "show_live_feed_check")
        assert not hasattr(dialog, "show_intensity_check")
        assert not hasattr(dialog, "show_histogram_check")
        assert not hasattr(dialog, "show_3d_check")
        assert not hasattr(dialog, "show_log_histogram_check")
        assert not hasattr(dialog, "auto_rescale_check")

        tab_titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        assert "Visualization" not in tab_titles
        assert tab_titles == ["Hardware", "UI"]


class TestHardwareTabLocking:
    """
    "Use Last Settings as Default" turns the Hardware tab's default-value
    fields into a read-only display of whatever was actually last used in
    Monitor Mode or Scan Mode, instead of a place to type in a default by
    hand. preview_size stays editable either way — it's a window-size
    preference, not a measurement default.
    """

    def test_fields_enabled_when_toggle_is_off(self, qtbot):
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", False)
        mgr.save()

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.camera_combo.isEnabled() is True
        assert dialog.exposure_spin.isEnabled() is True
        assert dialog.default_gain_spin.isEnabled() is True
        assert dialog.default_gain_factor_spin.isEnabled() is True
        assert dialog.preview_size_combo.isEnabled() is True

    def test_fields_disabled_when_toggle_is_on(self, qtbot):
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", True)
        mgr.save()

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.camera_combo.isEnabled() is False
        assert dialog.exposure_spin.isEnabled() is False
        assert dialog.default_gain_spin.isEnabled() is False
        assert dialog.default_gain_factor_spin.isEnabled() is False
        assert dialog.preview_size_combo.isEnabled() is True

    def test_populates_with_real_float_gain_values_without_crashing(self, qtbot):
        """
        monitor_gui.py/run_experiment_gui.py's gain/gain_factor widgets are
        QDoubleSpinBox (real decimal values like 3.7), but espi_app's own
        Default Gain/Gain Factor fields are QSpinBox (integer only) — the
        display has to round, not crash with a TypeError.
        """
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", True)
        mgr.save()

        settings_manager = _espi_full_algorithm_settings_manager()
        other = settings_manager.load_settings()
        other["last_used_dashboard"] = "monitor"
        other["monitor_default_gain"] = 3.7
        other["monitor_default_gain_factor"] = 12.5
        settings_manager.save_settings(other)

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.default_gain_spin.value() == 4
        # Python's round() is round-half-to-even ("banker's rounding"):
        # round(12.5) == 12, not 13.
        assert dialog.default_gain_factor_spin.value() == 12

    def test_populates_from_monitor_when_monitor_ran_last(self, qtbot):
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", True)
        mgr.save()

        settings_manager = _espi_full_algorithm_settings_manager()
        other = settings_manager.load_settings()
        other["last_used_dashboard"] = "monitor"
        other["default_camera_choice"] = "1"
        other["monitor_default_exposure"] = 0.09
        other["monitor_default_gain"] = 3
        other["monitor_default_gain_factor"] = 7
        settings_manager.save_settings(other)

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.camera_combo.currentData() == "1"
        assert dialog.exposure_spin.value() == pytest.approx(0.09)
        assert dialog.default_gain_spin.value() == 3
        assert dialog.default_gain_factor_spin.value() == 7

    def test_populates_from_scan_when_scan_ran_last(self, qtbot):
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", True)
        mgr.save()

        settings_manager = _espi_full_algorithm_settings_manager()
        other = settings_manager.load_settings()
        other["last_used_dashboard"] = "scan"
        other["default_camera_choice"] = "3"
        other["default_exposure"] = 0.02
        other["default_gain"] = 5
        other["default_gain_factor"] = 2
        settings_manager.save_settings(other)

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.camera_combo.currentData() == "3"
        assert dialog.exposure_spin.value() == pytest.approx(0.02)
        assert dialog.default_gain_spin.value() == 5
        assert dialog.default_gain_factor_spin.value() == 2

    def test_falls_back_to_espi_app_values_when_neither_dashboard_has_run(self, qtbot):
        mgr = SettingsManager()
        mgr.set("persistence.user_last_settings_as_default", True)
        mgr.set("hardware.default_camera_choice", "2")
        mgr.set("hardware.exposure_s", 0.05)
        mgr.save()

        settings_manager = _espi_full_algorithm_settings_manager()
        other = settings_manager.load_settings()
        other["last_used_dashboard"] = None
        settings_manager.save_settings(other)

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.camera_combo.currentData() == "2"
        assert dialog.exposure_spin.value() == pytest.approx(0.05)
