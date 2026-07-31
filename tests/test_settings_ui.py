"""
test_settings_ui.py
====================
Tests for settings_dialog.py — the Settings page UI components.

Focus: Load/save functionality, control state management, and settings persistence.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import DEFAULT_SETTINGS
from settings_dialog import LearnMoreDialog, SettingsPage


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestLearnMoreDialog:
    """Tests for LearnMoreDialog."""

    def test_learn_more_dialog_displays_content(self, qapp):
        """LearnMoreDialog should display HTML content."""
        dialog = LearnMoreDialog("Test Title", "<p>Test content</p>")
        assert dialog.windowTitle() == "Test Title"
        assert "Test content" in dialog.browser.toPlainText()
        dialog.close()


class TestSettingsPage:
    """Tests for SettingsPage."""

    def test_settings_page_initializes(self, qapp):
        """SettingsPage should create without errors."""
        page = SettingsPage()
        assert page is not None
        page.close()

    def test_settings_page_has_all_controls(self, qapp):
        """SettingsPage should have all required controls."""
        page = SettingsPage()
        
        # Grayscale controls
        assert hasattr(page, '_grayscale_radios')
        assert "standard" in page._grayscale_radios
        assert "single_channel" in page._grayscale_radios
        assert hasattr(page, '_color_combo')
        assert hasattr(page, '_backend_combo')
        
        # Camera controls
        assert hasattr(page, '_camera_radios')
        assert "1" in page._camera_radios
        assert "2" in page._camera_radios
        assert "3" in page._camera_radios
        assert hasattr(page, '_index_spin')
        
        # Capture controls
        assert hasattr(page, '_show_gain_checkbox')
        assert hasattr(page, 'start_freq_spin')
        assert hasattr(page, 'end_freq_spin')
        assert hasattr(page, 'step_spin')
        assert hasattr(page, 'n_averages_spin')
        assert hasattr(page, 'exposure_spin')
        assert hasattr(page, 'gain_spin')
        assert hasattr(page, 'gain_factor_spin')
        
        # Live monitoring
        assert hasattr(page, '_live_feed_checkbox')
        page.close()

    def test_load_settings_populates_controls(self, qapp):
        """load_settings should populate all controls with saved values."""
        with patch("settings_dialog.load_settings") as mock_load:
            mock_load.return_value = {
                "default_start_freq": 250.0,
                "default_exposure": 0.05,
                "default_camera_choice": "2",
                "grayscale_method": "single_channel",
                "show_gain": True,
                "show_live_feed_during_sweep": False,
            }

            page = SettingsPage()
            page.load_settings()

            # Verify controls were updated
            assert page.start_freq_spin.value() == 250.0
            assert page.exposure_spin.value() == 0.05
            assert page._camera_radios["2"].isChecked()
            assert page._grayscale_radios["single_channel"].isChecked()
            assert page._show_gain_checkbox.isChecked()
            assert not page._live_feed_checkbox.isChecked()
            page.close()

    def test_save_settings_writes_values(self, qapp):
        """save_settings should write current control values."""
        with patch("settings_dialog.save_settings") as mock_save:
            mock_save.return_value = True

            page = SettingsPage()
            page.start_freq_spin.setValue(350.0)
            page.exposure_spin.setValue(0.03)
            page._camera_radios["3"].setChecked(True)
            page.save_settings()

            # Verify save was called with updated settings
            mock_save.assert_called_once()
            saved_settings = mock_save.call_args[0][0]
            assert saved_settings["default_start_freq"] == 350.0
            assert saved_settings["default_exposure"] == 0.03
            assert saved_settings["default_camera_choice"] == "3"
            page.close()

    def test_spin_box_ranges_are_reasonable(self, qapp):
        """Spin boxes should have reasonable ranges."""
        page = SettingsPage()

        # Exposure should be positive
        assert page.exposure_spin.minimum() > 0

        # n_averages should be at least 1
        assert page.n_averages_spin.minimum() >= 1

        # Frequencies should allow reasonable values
        assert page.start_freq_spin.minimum() >= 0
        assert page.end_freq_spin.minimum() >= 0
        assert page.step_spin.minimum() > 0

        page.close()

    def test_radio_button_groups_work(self, qapp):
        """Radio button groups should be mutually exclusive."""
        page = SettingsPage()

        # Grayscale radios should be exclusive
        page._grayscale_radios["standard"].setChecked(True)
        assert page._grayscale_radios["standard"].isChecked()
        assert not page._grayscale_radios["single_channel"].isChecked()

        page._grayscale_radios["single_channel"].setChecked(True)
        assert not page._grayscale_radios["standard"].isChecked()
        assert page._grayscale_radios["single_channel"].isChecked()

        # Camera radios should be exclusive
        page._camera_radios["1"].setChecked(True)
        assert page._camera_radios["1"].isChecked()
        assert not page._camera_radios["2"].isChecked()

        page.close()

    def test_combo_box_options(self, qapp):
        """Combo boxes should have appropriate options."""
        page = SettingsPage()

        # Color combo should have RGB options
        assert page._color_combo.count() == 3
        color_options = [page._color_combo.itemText(i) for i in range(3)]
        assert "Red (R)" in color_options
        assert "Green (G)" in color_options
        assert "Blue (B)" in color_options

        # Backend combo should have three implementations
        assert page._backend_combo.count() == 3
        page.close()


class TestSettingsIntegration:
    """Integration tests for settings workflow."""

    def test_full_settings_save_and_load_workflow(self, qapp):
        """User should be able to modify settings and save/load them."""
        with patch("settings_dialog.load_settings") as mock_load:
            with patch("settings_dialog.save_settings") as mock_save:
                mock_load.return_value = DEFAULT_SETTINGS.copy()
                mock_save.return_value = True

                page = SettingsPage()
                page.load_settings()

                # Simulate user changing settings
                page.start_freq_spin.setValue(200.0)
                page.end_freq_spin.setValue(2000.0)
                page._camera_radios["3"].setChecked(True)
                page._show_gain_checkbox.setChecked(True)

                # Save changes
                success = page.save_settings()

                assert success is True
                mock_save.assert_called_once()
                
                # Verify all changes are in the saved settings
                saved_settings = mock_save.call_args[0][0]
                assert saved_settings["default_start_freq"] == 200.0
                assert saved_settings["default_end_freq"] == 2000.0
                assert saved_settings["default_camera_choice"] == "3"
                assert saved_settings["show_gain"] is True
                
                page.close()

    def test_default_camera_index_updates_correctly(self, qapp):
        """Camera index should update when camera choice changes."""
        page = SettingsPage()

        # Default to USB (camera 2)
        page._camera_radios["2"].setChecked(True)
        page._index_spin.setValue(1)
        
        # Switch to Allied Vision
        page._camera_radios["3"].setChecked(True)
        assert page._index_spin.value() == 1
        
        page.close()

    def test_settings_persistence_mock(self, qapp):
        """Settings should be correctly serialized for persistence."""
        with patch("settings_dialog.load_settings") as mock_load:
            with patch("settings_dialog.save_settings") as mock_save:
                mock_load.return_value = DEFAULT_SETTINGS.copy()
                mock_save.return_value = True

                page = SettingsPage()
                page.load_settings()
                page.save_settings()

                # Get the saved settings
                saved = mock_save.call_args[0][0]
                
                # All required keys should be present
                required_keys = set(DEFAULT_SETTINGS.keys())
                assert set(saved.keys()) >= required_keys
                
                page.close()
