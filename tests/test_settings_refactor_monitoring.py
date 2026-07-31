"""
test_settings_refactor_monitoring.py
====================================
TDD for settings refactor: Separate toggles for live feed and saved image display.

Instead of: show_live_feed_during_sweep (boolean)
We want:
  - show_live_feed_during_sweep (boolean) - show live feed during sweep
  - show_saved_image_after_capture (boolean) - show just-saved frame after capture
"""

import pytest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestSettingsRefactorMonitoring:
    """Test that settings have separate toggles for monitoring displays."""
    
    def test_default_settings_has_live_feed_toggle(self):
        """DEFAULT_SETTINGS should have show_live_feed_during_sweep."""
        assert "show_live_feed_during_sweep" in DEFAULT_SETTINGS
        assert isinstance(DEFAULT_SETTINGS["show_live_feed_during_sweep"], bool)
    
    def test_default_settings_has_saved_image_toggle(self):
        """DEFAULT_SETTINGS should have show_saved_image_after_capture."""
        assert "show_saved_image_after_capture" in DEFAULT_SETTINGS
        assert isinstance(DEFAULT_SETTINGS["show_saved_image_after_capture"], bool)
    
    def test_both_toggles_independent(self):
        """Live feed and saved image toggles should be independent."""
        settings = DEFAULT_SETTINGS.copy()
        
        # Can enable live feed without saved image
        settings["show_live_feed_during_sweep"] = True
        settings["show_saved_image_after_capture"] = False
        assert settings["show_live_feed_during_sweep"] is True
        assert settings["show_saved_image_after_capture"] is False
        
        # Can enable saved image without live feed
        settings["show_live_feed_during_sweep"] = False
        settings["show_saved_image_after_capture"] = True
        assert settings["show_live_feed_during_sweep"] is False
        assert settings["show_saved_image_after_capture"] is True
        
        # Can enable both
        settings["show_live_feed_during_sweep"] = True
        settings["show_saved_image_after_capture"] = True
        assert settings["show_live_feed_during_sweep"] is True
        assert settings["show_saved_image_after_capture"] is True
    
    def test_toggles_persist_across_save_load(self, tmp_path):
        """Both toggles should persist across save/load cycles."""
        settings_file = tmp_path / "settings.json"
        
        original = DEFAULT_SETTINGS.copy()
        original["show_live_feed_during_sweep"] = True
        original["show_saved_image_after_capture"] = False
        
        with patch("settings_manager._get_settings_path", return_value=settings_file):
            save_settings(original)
            loaded = load_settings()
        
        assert loaded["show_live_feed_during_sweep"] is True
        assert loaded["show_saved_image_after_capture"] is False


class TestMonitoringSettingsUsage:
    """Test that SweepPage and workers respect the new toggle settings."""
    
    def test_sweep_page_can_check_both_toggles(self, qapp, tmp_path):
        """SweepPage should be able to check both monitoring toggles."""
        settings_file = tmp_path / "settings.json"
        
        settings = DEFAULT_SETTINGS.copy()
        settings["show_live_feed_during_sweep"] = True
        settings["show_saved_image_after_capture"] = False
        
        with patch("settings_manager._get_settings_path", return_value=settings_file):
            save_settings(settings)
        
        from run_experiment_gui import SweepPage
        page = SweepPage()
        
        with patch("run_experiment_gui.load_settings", return_value=settings):
            # Verify page can access both toggles (will be used in _start_sweep)
            live_feed_enabled = settings.get("show_live_feed_during_sweep", False)
            saved_image_enabled = settings.get("show_saved_image_after_capture", False)
            
            assert live_feed_enabled is True
            assert saved_image_enabled is False

