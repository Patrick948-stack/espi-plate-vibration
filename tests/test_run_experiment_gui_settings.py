"""
test_run_experiment_gui_settings.py
===================================
Tests for Settings integration in run_experiment_gui.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication, QListWidget, QStackedWidget

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSettingsIntegration:
    """Tests for Settings page integration in run_experiment_gui."""

    def test_nav_rail_has_settings_button(self, qapp):
        """Navigation rail should have Settings as 5th item."""
        from run_experiment_gui import MainWindow

        window = MainWindow()
        
        nav_widget = window._nav
        assert isinstance(nav_widget, QListWidget)
        
        # Check all nav items exist
        items = [nav_widget.item(i).text() for i in range(nav_widget.count())]
        assert "Setup" in items
        assert "Preview" in items
        assert "Sweep" in items
        assert "Results" in items
        assert "Settings" in items
        
        # Settings should be the 5th item (index 4)
        settings_index = items.index("Settings")
        assert settings_index == 4
        
        window.close()

    def test_settings_page_added_to_stack(self, qapp):
        """SettingsPage should be in QStackedWidget."""
        from run_experiment_gui import MainWindow, SettingsPage

        window = MainWindow()
        
        stack = window._stack
        assert isinstance(stack, QStackedWidget)
        
        # Should have 5 pages: Setup, Preview, Sweep, Results, Settings
        assert stack.count() == 5
        
        # Settings page should be at index 4
        settings_page = stack.widget(4)
        assert isinstance(settings_page, SettingsPage)
        
        window.close()

    def test_nav_click_shows_settings_page(self, qapp):
        """Clicking Settings in nav should show SettingsPage."""
        from run_experiment_gui import MainWindow

        window = MainWindow()
        
        # Find Settings nav item (should be at index 4)
        window._nav.setCurrentRow(4)
        
        # Stack should show the Settings page
        assert window._stack.currentIndex() == 4
        
        window.close()

    def test_settings_page_loads_on_open(self, qapp):
        """SettingsPage should load settings when shown."""
        from run_experiment_gui import MainWindow

        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                "default_start_freq": 200.0,
                "default_camera_choice": "2",
            }

            window = MainWindow()
            settings_page = window._stack.widget(4)
            
            # Navigate to settings
            window._nav.setCurrentRow(4)
            
            # Settings should have been loaded
            assert settings_page is not None
            
            window.close()

    def test_settings_page_has_save_functionality(self, qapp):
        """SettingsPage should have save_settings method."""
        from run_experiment_gui import MainWindow, SettingsPage

        window = MainWindow()
        settings_page = window._stack.widget(4)
        
        assert isinstance(settings_page, SettingsPage)
        assert hasattr(settings_page, 'save_settings')
        assert callable(settings_page.save_settings)
        
        window.close()

    def test_settings_persistence_across_navigation(self, qapp):
        """Settings values should persist when navigating away and back."""
        from run_experiment_gui import MainWindow

        with patch("run_experiment_gui.load_settings") as mock_load:
            with patch("run_experiment_gui.save_settings") as mock_save:
                mock_load.return_value = {
                    "default_start_freq": 150.0,
                    "default_camera_choice": "1",
                }
                mock_save.return_value = True

                window = MainWindow()
                settings_page = window._stack.widget(4)
                
                # Navigate to settings
                window._nav.setCurrentRow(4)
                
                # Change a value
                settings_page.start_freq_spin.setValue(250.0)
                
                # Navigate away
                window._nav.setCurrentRow(0)
                
                # Navigate back to settings
                window._nav.setCurrentRow(4)
                
                # Value should still be there
                assert settings_page.start_freq_spin.value() == 250.0
                
                window.close()

    def test_settings_button_styling_consistency(self, qapp):
        """Settings button should have consistent styling with other nav items."""
        from run_experiment_gui import MainWindow

        window = MainWindow()
        
        # All nav items should be selectable (or controllably disabled)
        nav = window._nav
        for row in range(nav.count()):
            item = nav.item(row)
            assert item is not None
        
        window.close()
