"""
test_setup_page_defaults.py
===========================
Tests for SetupPage loading default settings from settings_manager.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import DEFAULT_SETTINGS


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSetupPageDefaults:
    """Tests for SetupPage loading settings as defaults."""

    def test_setup_page_loads_all_defaults(self, qapp):
        """SetupPage should load all settings defaults when created."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            test_settings = {
                "default_start_freq": 200.0,
                "default_end_freq": 2000.0,
                "default_step_size": 50.0,
                "default_n_averages": 10,
                "default_exposure": 0.05,
                "default_gain": 2.0,
                "default_gain_factor": 5.0,
                "default_camera_choice": "1",
                "show_gain": True,
            }
            mock_load.return_value = test_settings

            page = SetupPage()

            # Verify all settings were loaded correctly
            assert page.start_freq_spin.value() == 200.0, "Start freq not loaded"
            assert page.end_freq_spin.value() == 2000.0, "End freq not loaded"
            assert page.step_spin.value() == 50.0, "Step not loaded"
            assert page.n_averages_spin.value() == 10, "N_averages not loaded"
            assert page.exposure_spin.value() == 0.05, "Exposure not loaded"
            assert page.gain_spin.value() == 2.0, "Gain not loaded"
            assert page.gain_factor_spin.value() == 5.0, "Gain_factor not loaded"
            assert page.camera_choice() == "1", "Camera choice not loaded"
            
            page.close()

    def test_setup_page_camera_choices_from_settings(self, qapp):
        """SetupPage should load different camera choices from settings."""
        from run_experiment_gui import SetupPage

        for camera_choice in ["1", "2", "3"]:
            with patch("run_experiment_gui.load_settings") as mock_load:
                mock_load.return_value = {
                    **DEFAULT_SETTINGS,
                    "default_camera_choice": camera_choice,
                }

                page = SetupPage()
                assert page.camera_choice() == camera_choice, f"Camera {camera_choice} not loaded"
                page.close()

    def test_setup_page_frequency_range_from_settings(self, qapp):
        """SetupPage should load complete frequency sweep range."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                **DEFAULT_SETTINGS,
                "default_start_freq": 50.0,
                "default_end_freq": 5000.0,
                "default_step_size": 25.0,
            }

            page = SetupPage()
            assert page.start_freq_spin.value() == 50.0
            assert page.end_freq_spin.value() == 5000.0
            assert page.step_spin.value() == 25.0
            page.close()

    def test_setup_page_averaging_from_settings(self, qapp):
        """SetupPage should load frames-per-frequency averaging."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                **DEFAULT_SETTINGS,
                "default_n_averages": 15,
            }

            page = SetupPage()
            assert page.n_averages_spin.value() == 15
            page.close()

    def test_setup_page_exposure_and_gain_from_settings(self, qapp):
        """SetupPage should load exposure and gain settings."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                **DEFAULT_SETTINGS,
                "default_exposure": 0.03,
                "default_gain": 5.0,
            }

            page = SetupPage()
            assert page.exposure_spin.value() == 0.03
            assert page.gain_spin.value() == 5.0
            page.close()

    def test_setup_page_gain_factor_from_settings(self, qapp):
        """SetupPage should load gain_factor (difference amplification)."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                **DEFAULT_SETTINGS,
                "default_gain_factor": 20.0,
            }

            page = SetupPage()
            assert page.gain_factor_spin.value() == 20.0
            page.close()

    def test_setup_page_fallback_to_constants_if_missing_keys(self, qapp):
        """SetupPage should use sensible defaults if settings keys missing."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            # Return minimal settings
            mock_load.return_value = {
                "default_camera_choice": "2",
            }

            page = SetupPage()

            # Should still have reasonable values for everything
            assert page.start_freq_spin.value() > 0
            assert page.end_freq_spin.value() > 0
            assert page.step_spin.value() > 0
            assert page.n_averages_spin.value() > 0
            assert page.exposure_spin.value() > 0
            assert page.gain_factor_spin.value() > 0
            
            page.close()

    def test_setup_page_returns_loaded_values_in_params(self, qapp):
        """SetupPage.get_params() should return values loaded from settings."""
        from run_experiment_gui import SetupPage

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                "default_start_freq": 150.0,
                "default_end_freq": 1500.0,
                "default_step_size": 75.0,
                "default_n_averages": 8,
                "default_exposure": 0.02,
                "default_gain": 1.5,
                "default_gain_factor": 2.5,
            }

            page = SetupPage()
            params = page.get_params()

            # Verify get_params returns the loaded values
            assert params["start_freq"] == 150.0
            assert params["end_freq"] == 1500.0
            assert params["step"] == 75.0
            assert params["n_averages"] == 8
            assert params["exposure"] == 0.02
            assert params["gain"] == 1.5
            assert params["gain_factor"] == 2.5
            
            page.close()
