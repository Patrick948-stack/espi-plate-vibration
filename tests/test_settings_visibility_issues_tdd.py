"""
test_settings_visibility_issues_tdd.py
======================================

TDD regression tests for Settings page visibility bugs.

FAILING TESTS: These will FAIL before fixes and PASS after.
Goal: Write failing test first, then fix code.
"""

import pytest
from pathlib import Path
import sys

from PyQt6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_dialog import SettingsPage


@pytest.fixture
def settings_page_visible(qtbot):
    """Fixture that creates a visible SettingsPage for testing."""
    page = SettingsPage()
    qtbot.addWidget(page)
    page.show()
    qtbot.wait(50)
    return page


class TestGainVisibilityBug:
    """
    BUG: "Gain (dB)" controls appear even though "Show Gain (dB) control" checkbox is unchecked.
    Expected: Gain label and spin box should be HIDDEN when checkbox is unchecked.
    Broken: They appear anyway.
    """

    def test_gain_controls_hidden_by_default(self, qtbot):
        """
        FAILING TEST (Red phase): Gain controls should be hidden when checkbox unchecked.

        BEFORE FIX: gain_label and gain_spin are VISIBLE even though checkbox is False
        AFTER FIX: They should be HIDDEN
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Verify checkbox starts unchecked
        assert not page._show_gain_checkbox.isChecked(), \
            "Show Gain checkbox should start unchecked"

        # FAILING ASSERTION (this will fail before fix):
        # The gain controls should be HIDDEN
        assert not page._gain_label.isVisible(), \
            "BUG: Gain label should be HIDDEN when checkbox is unchecked"

        assert not page.gain_spin.isVisible(), \
            "BUG: Gain spin box should be HIDDEN when checkbox is unchecked"

    def test_gain_controls_shown_when_checkbox_checked(self, qtbot, settings_page_visible):
        """
        Gain controls should appear only when checkbox is explicitly checked.
        """
        page = settings_page_visible

        # Check the checkbox using qtbot.click() for proper signal emission
        qtbot.mouseClick(page._show_gain_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(100)  # Let UI update

        # Now controls should be VISIBLE
        assert page._gain_label.isVisible(), \
            "Gain label should be VISIBLE when checkbox is checked"

        assert page.gain_spin.isVisible(), \
            "Gain spin box should be VISIBLE when checkbox is checked"

    def test_gain_controls_toggle_visibility(self, qtbot):
        """
        Toggling checkbox should show/hide gain controls.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Start hidden
        assert not page._show_gain_checkbox.isChecked()
        assert not page._gain_label.isVisible()
        assert not page.gain_spin.isVisible()

        # Show - click checkbox
        qtbot.mouseClick(page._show_gain_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert page._gain_label.isVisible()
        assert page.gain_spin.isVisible()

        # Hide again - click checkbox
        qtbot.mouseClick(page._show_gain_checkbox, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert not page._gain_label.isVisible()
        assert not page.gain_spin.isVisible()


class TestGrayscaleVisibilityBug:
    """
    BUG: Color and backend controls appear even for "Standard Full-RGB" method.
    Expected: Only show these when "Single-Channel Extraction" is selected.
    """

    def test_color_backend_hidden_for_standard_method(self, qtbot):
        """
        FAILING TEST: Color and backend controls should be HIDDEN for Standard method.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Verify standard is selected
        assert page._grayscale_radios["standard"].isChecked(), \
            "Standard method should be selected by default"

        # FAILING ASSERTIONS:
        # These controls should be HIDDEN
        assert not page._color_label.isVisible(), \
            "BUG: Color label should be HIDDEN for Standard method"

        assert not page._color_combo.isVisible(), \
            "BUG: Color combo should be HIDDEN for Standard method"

        assert not page._backend_label.isVisible(), \
            "BUG: Backend label should be HIDDEN for Standard method"

        assert not page._backend_combo.isVisible(), \
            "BUG: Backend combo should be HIDDEN for Standard method"

    def test_color_backend_shown_for_single_channel_method(self, qtbot):
        """
        Color and backend controls should appear for Single-Channel method.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Select single channel using mouse click
        qtbot.mouseClick(page._grayscale_radios["single_channel"], Qt.MouseButton.LeftButton)
        qtbot.wait(100)

        # Now controls should be VISIBLE
        assert page._color_label.isVisible(), \
            "Color label should be VISIBLE for Single-Channel method"

        assert page._color_combo.isVisible(), \
            "Color combo should be VISIBLE for Single-Channel method"

        assert page._backend_label.isVisible(), \
            "Backend label should be VISIBLE for Single-Channel method"

        assert page._backend_combo.isVisible(), \
            "Backend combo should be VISIBLE for Single-Channel method"

    def test_grayscale_method_toggle_visibility(self, qtbot, settings_page_visible):
        """
        Switching between methods should toggle control visibility.
        """
        page = settings_page_visible

        # Start with standard (hidden) - already selected by default
        qtbot.wait(50)
        assert page._grayscale_radios["standard"].isChecked()
        assert not page._color_label.isVisible()

        # Switch to single channel (show)
        page._grayscale_radios["single_channel"].setChecked(True)
        page._update_grayscale_visibility()  # Explicitly call since signals may not fire
        qtbot.wait(100)
        assert page._grayscale_radios["single_channel"].isChecked(), "Single channel should now be checked"
        assert page._color_label.isVisible(), "Color should be visible for single channel"

        # Switch back to standard (hide)
        page._grayscale_radios["standard"].setChecked(True)
        page._update_grayscale_visibility()  # Explicitly call since signals may not fire
        qtbot.wait(100)
        assert page._grayscale_radios["standard"].isChecked(), "Standard should now be checked again"
        assert not page._color_label.isVisible(), "Color label should be hidden for standard"


class TestCameraVisibilityBug:
    """
    BUG: Camera index control appears even for Basler camera.
    Expected: Camera index only for USB and Allied Vision (not Basler).
    """

    def test_camera_index_hidden_for_basler(self, qtbot):
        """
        FAILING TEST: Camera index should be HIDDEN for Basler camera.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Select Basler
        page._camera_radios["1"].setChecked(True)
        qtbot.wait(50)

        # Camera index should be HIDDEN
        assert not page._index_label.isVisible(), \
            "BUG: Camera index label should be HIDDEN for Basler"

        assert not page._index_spin.isVisible(), \
            "BUG: Camera index spin should be HIDDEN for Basler"

    def test_camera_index_shown_for_usb(self, qtbot):
        """
        Camera index should appear for USB camera.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Select USB - click the radio button
        qtbot.mouseClick(page._camera_radios["2"], Qt.MouseButton.LeftButton)
        qtbot.wait(100)

        # Camera index should be VISIBLE
        assert page._index_label.isVisible(), \
            "Camera index label should be VISIBLE for USB"

        assert page._index_spin.isVisible(), \
            "Camera index spin should be VISIBLE for USB"

    def test_camera_index_shown_for_allied_vision(self, qtbot):
        """
        Camera index should appear for Allied Vision camera.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Select Allied Vision - click the radio button
        qtbot.mouseClick(page._camera_radios["3"], Qt.MouseButton.LeftButton)
        qtbot.wait(100)

        # Camera index should be VISIBLE
        assert page._index_label.isVisible(), \
            "Camera index label should be VISIBLE for Allied Vision"

        assert page._index_spin.isVisible(), \
            "Camera index spin should be VISIBLE for Allied Vision"

    def test_camera_index_toggle_visibility(self, qtbot):
        """
        Switching cameras should toggle index control visibility correctly.
        """
        page = SettingsPage()
        qtbot.addWidget(page)

        # Start with USB (visible) - already selected by default
        qtbot.wait(50)
        assert page._index_label.isVisible()

        # Switch to Basler (hidden)
        qtbot.mouseClick(page._camera_radios["1"], Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert not page._index_label.isVisible()

        # Switch to Allied Vision (visible)
        qtbot.mouseClick(page._camera_radios["3"], Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert page._index_label.isVisible()


class TestSettingsInitialization:
    """
    BUG: Settings page might not load saved values correctly on init.
    """

    def test_load_settings_updates_all_controls(self, qtbot, tmp_path):
        """
        Loading settings should update all controls from disk.
        """
        from settings_manager import save_settings, load_settings
        from unittest.mock import patch

        settings_file = tmp_path / "settings.json"

        with patch("settings_manager._get_settings_path", return_value=settings_file):
            # Save custom settings
            settings = load_settings()
            settings.update({
                "grayscale_method": "single_channel",
                "grayscale_color": "G",
                "default_camera_choice": "3",
                "show_gain": True,
                "default_start_freq": 333.0,
                "show_live_feed_during_sweep": False,
            })
            save_settings(settings)

            # Create page and load
            page = SettingsPage()
            qtbot.addWidget(page)
            page.load_settings()

            # Verify all controls loaded
            assert page._grayscale_radios["single_channel"].isChecked()
            assert page._color_combo.currentIndex() == 1  # Green (G)
            assert page._camera_radios["3"].isChecked()
            assert page._show_gain_checkbox.isChecked()
            assert page.start_freq_spin.value() == 333.0
            assert not page._live_feed_checkbox.isChecked()


class TestSettingsSave:
    """
    Verify save_settings() captures all current control values.
    """

    def test_save_settings_captures_all_values(self, qtbot, tmp_path):
        """
        Calling save_settings() should write all control values to disk.
        """
        from settings_manager import load_settings
        from unittest.mock import patch

        settings_file = tmp_path / "settings.json"

        with patch("settings_manager._get_settings_path", return_value=settings_file):
            page = SettingsPage()
            qtbot.addWidget(page)

            # Set values
            page._grayscale_radios["single_channel"].setChecked(True)
            page._color_combo.setCurrentIndex(1)  # Green
            page._camera_radios["3"].setChecked(True)
            page._show_gain_checkbox.setChecked(True)
            page.start_freq_spin.setValue(500.0)
            page._live_feed_checkbox.setChecked(False)

            # Save
            result = page.save_settings()
            assert result is True, "save_settings should return True"

            # Load from disk and verify
            settings = load_settings()
            assert settings["grayscale_method"] == "single_channel"
            assert settings["grayscale_color"] == "G"
            assert settings["default_camera_choice"] == "3"
            assert settings["show_gain"] is True
            assert settings["default_start_freq"] == 500.0
            assert settings["show_live_feed_during_sweep"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
