"""
test_main_window.py
Tests for espi_app/main_window.py (LandingPage).

Regression tests for the Monitor Mode / Scan Mode buttons, which used to
just show a "Not yet implemented" QMessageBox instead of actually opening
monitor_gui.py / run_experiment_gui.py's dashboards. Also covers the help
text emoji removal, and the shared light/dark theme system: one theme
choice now styles the landing page and both dashboards together (instead
of each dashboard forcing its own fixed dark look), including icon colors
and settings persisted across sessions.
"""

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from espi_app.main_window import LandingPage
from espi_app.settings import SettingsManager
from espi_app.styles import apply_theme


# ===========================================================================
# Monitor Mode button
# ===========================================================================

class TestMonitorModeLaunch:
    def test_monitor_button_opens_a_real_monitor_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)

        assert window._monitor_window is not None
        assert window._monitor_window.isVisible()
        assert not window.monitor_button.isEnabled()

        window._monitor_window.close()
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)

    def test_closing_monitor_window_re_enables_the_button(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)
        window._monitor_window.close()
        # WA_DeleteOnClose defers the actual C++ deletion (and the
        # destroyed signal) to the next event loop tick, so it will not
        # have happened yet immediately after close() returns.
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)

        assert window.monitor_button.isEnabled()

    def test_clicking_monitor_twice_does_not_open_a_second_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)
        first_window = window._monitor_window

        # The button is disabled after the first click, so a real second
        # mouse click would be ignored by Qt itself. Call the handler
        # directly to test _launch_child_window's own guard too.
        window._on_monitor_clicked()

        assert window._monitor_window is first_window
        first_window.close()
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)

    def test_monitor_launch_failure_shows_error_and_re_enables_button(
        self, qtbot, monkeypatch
    ):
        window = LandingPage()
        qtbot.addWidget(window)

        def _boom(self):
            raise RuntimeError("no camera SDK installed")

        monkeypatch.setattr(LandingPage, "_create_monitor_window", _boom)

        captured = {}

        def _fake_critical(parent, title, text):
            captured["title"] = title
            captured["text"] = text

        monkeypatch.setattr(QMessageBox, "critical", staticmethod(_fake_critical))

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)

        assert window._monitor_window is None
        assert window.monitor_button.isEnabled()
        assert "no camera SDK installed" in captured["text"]

    def test_monitor_window_keeps_the_current_app_theme(self, qtbot):
        # monitor_gui.MainWindow reads the same bridged theme espi_app
        # just synced to ~/.espi/settings.json, so opening it should not
        # change the app's stylesheet away from what espi_app set. It
        # does still append its own nav-item-height rule on top (see
        # monitor_gui._stylesheet_for()), so the two are not expected to
        # match exactly — only the shared color tokens matter here.
        app = QApplication.instance()
        window = LandingPage()
        qtbot.addWidget(window)
        # ui.theme is what _sync_settings_to_espi_full_algorithm() bridges
        # from, so it (not just the live QApplication stylesheet) must
        # agree with "dark" for this scenario to be realistic.
        window.settings_manager.set("ui.theme", "dark")
        apply_theme(app, "dark")
        dark_stylesheet = app.styleSheet()

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)
        assert app.styleSheet().startswith(dark_stylesheet)

        window._monitor_window.close()
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)


# ===========================================================================
# Scan Mode button
# ===========================================================================

class TestScanModeLaunch:
    def test_scan_button_opens_a_real_scan_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)

        assert window._scan_window is not None
        assert window._scan_window.isVisible()
        assert not window.scan_button.isEnabled()

        window._scan_window.close()
        qtbot.waitUntil(lambda: window._scan_window is None, timeout=2000)

    def test_closing_scan_window_re_enables_the_button(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
        window._scan_window.close()
        qtbot.waitUntil(lambda: window._scan_window is None, timeout=2000)

        assert window.scan_button.isEnabled()

    def test_clicking_scan_twice_does_not_open_a_second_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
        first_window = window._scan_window

        window._on_scan_clicked()

        assert window._scan_window is first_window
        first_window.close()
        qtbot.waitUntil(lambda: window._scan_window is None, timeout=2000)

    def test_scan_window_keeps_the_current_app_theme(self, qtbot):
        app = QApplication.instance()
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("ui.theme", "light")
        apply_theme(app, "light")
        light_stylesheet = app.styleSheet()

        qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)
        assert app.styleSheet() == light_stylesheet

        window._scan_window.close()
        qtbot.waitUntil(lambda: window._scan_window is None, timeout=2000)


# ===========================================================================
# Help text (emoji removal)
# ===========================================================================

class TestHelpText:
    def test_help_text_has_no_emoji(self, qtbot, monkeypatch):
        window = LandingPage()
        qtbot.addWidget(window)

        captured = {}

        def _fake_information(parent, title, text):
            captured["text"] = text

        monkeypatch.setattr(QMessageBox, "information", staticmethod(_fake_information))

        qtbot.mouseClick(window.help_button, Qt.MouseButton.LeftButton)

        for emoji in ("\U0001F4F9", "\U0001F4CA", "⚙"):
            assert emoji not in captured["text"]

    def test_help_text_still_describes_both_modes(self, qtbot, monkeypatch):
        window = LandingPage()
        qtbot.addWidget(window)

        captured = {}
        monkeypatch.setattr(
            QMessageBox,
            "information",
            staticmethod(lambda parent, title, text: captured.setdefault("text", text)),
        )

        qtbot.mouseClick(window.help_button, Qt.MouseButton.LeftButton)

        assert "Monitor Camera" in captured["text"]
        assert "Run Experiment" in captured["text"]


# ===========================================================================
# Theme bridge into ESPI Full Algorithm's own settings file
# ===========================================================================

class TestThemeBridge:
    def test_theme_and_preview_size_always_bridge(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("ui.theme", "dark")
        window.settings_manager.set("hardware.preview_size", "Large")
        window.settings_manager.set("persistence.user_last_settings_as_default", False)

        window._sync_settings_to_espi_full_algorithm()

        import settings_manager as espi_settings_manager
        bridged = espi_settings_manager.load_settings()
        assert bridged["theme"] == "dark"
        assert bridged["preview_size"] == "Large"

    def test_use_last_settings_as_default_flag_always_bridges(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        import settings_manager as espi_settings_manager

        window.settings_manager.set("persistence.user_last_settings_as_default", False)
        window._sync_settings_to_espi_full_algorithm()
        assert espi_settings_manager.load_settings()["use_last_settings_as_default"] is False

        window.settings_manager.set("persistence.user_last_settings_as_default", True)
        window._sync_settings_to_espi_full_algorithm()
        assert espi_settings_manager.load_settings()["use_last_settings_as_default"] is True

    def test_sync_never_touches_camera_exposure_gain(self, qtbot):
        """
        _sync_settings_to_espi_full_algorithm() (called on every dashboard
        launch and every theme change) must never push camera/exposure/gain
        — only _push_hardware_defaults_to_espi_full_algorithm() does that,
        and only from an explicit Settings Save. Otherwise, simply opening
        Monitor Mode again would silently clobber a value the user set
        locally inside that dashboard's own settings.
        """
        import settings_manager as espi_settings_manager

        other = espi_settings_manager.load_settings()
        other["default_camera_choice"] = "3"
        other["monitor_default_exposure"] = 0.42
        espi_settings_manager.save_settings(other)

        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("hardware.default_camera_choice", "1")
        window.settings_manager.set("hardware.exposure_s", 0.01)

        window._sync_settings_to_espi_full_algorithm()

        bridged = espi_settings_manager.load_settings()
        assert bridged["default_camera_choice"] == "3"
        assert bridged["monitor_default_exposure"] == pytest.approx(0.42)

    def test_push_hardware_defaults_writes_both_dashboards_keys(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("hardware.default_camera_choice", "3")
        window.settings_manager.set("hardware.exposure_s", 0.02)
        window.settings_manager.set("persistence.default_gain", 5)
        window.settings_manager.set("persistence.default_gain_factor", 8)
        window.settings_manager.save()

        window._push_hardware_defaults_to_espi_full_algorithm()

        import settings_manager as espi_settings_manager
        bridged = espi_settings_manager.load_settings()
        assert bridged["default_camera_choice"] == "3"
        assert bridged["default_exposure"] == pytest.approx(0.02)
        assert bridged["default_gain"] == pytest.approx(5)
        assert bridged["default_gain_factor"] == pytest.approx(8)
        assert bridged["monitor_default_exposure"] == pytest.approx(0.02)
        assert bridged["monitor_default_gain"] == pytest.approx(5)
        assert bridged["monitor_default_gain_factor"] == pytest.approx(8)

    def test_opening_monitor_mode_does_not_push_hardware_defaults(self, qtbot):
        """No clobber-on-launch: opening a dashboard must not overwrite
        camera/exposure/gain the user set locally inside it."""
        import settings_manager as espi_settings_manager

        other = espi_settings_manager.load_settings()
        other["default_camera_choice"] = "3"
        espi_settings_manager.save_settings(other)

        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("hardware.default_camera_choice", "1")

        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)

        assert espi_settings_manager.load_settings()["default_camera_choice"] == "3"
        window._monitor_window.close()
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)

    def test_settings_save_pushes_hardware_defaults_when_unlocked(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        from espi_app.settings_dialog import SettingsDialog

        dialog = SettingsDialog(parent=window)
        qtbot.addWidget(dialog)
        dialog.hardware_defaults_changed.connect(
            window._push_hardware_defaults_to_espi_full_algorithm
        )
        dialog.camera_combo.setCurrentIndex(dialog.camera_combo.findData("3"))

        dialog._on_save()

        import settings_manager as espi_settings_manager
        assert espi_settings_manager.load_settings()["default_camera_choice"] == "3"

    def test_settings_save_does_not_push_hardware_defaults_when_locked(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("persistence.user_last_settings_as_default", True)
        window.settings_manager.save()

        import settings_manager as espi_settings_manager

        other = espi_settings_manager.load_settings()
        other["default_camera_choice"] = "3"
        espi_settings_manager.save_settings(other)

        from espi_app.settings_dialog import SettingsDialog

        dialog = SettingsDialog(parent=window)
        qtbot.addWidget(dialog)
        dialog.hardware_defaults_changed.connect(
            window._push_hardware_defaults_to_espi_full_algorithm
        )

        dialog._on_save()

        assert espi_settings_manager.load_settings()["default_camera_choice"] == "3"

    def test_theme_override_wins_over_stale_settings_manager(self, qtbot):
        # _on_theme_changed passes theme_override because it fires while
        # self.settings_manager may not yet reflect the just-saved theme
        # (see the docstring on _sync_settings_to_espi_full_algorithm).
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("ui.theme", "light")

        window._sync_settings_to_espi_full_algorithm(theme_override="dark")

        import settings_manager as espi_settings_manager
        assert espi_settings_manager.load_settings()["theme"] == "dark"


# ===========================================================================
# Live theme refresh while Monitor/Scan windows are already open
# ===========================================================================

class TestLiveThemeRefresh:
    def test_changing_theme_refreshes_landing_page_icons(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        before = window.monitor_button.icon()
        window._on_theme_changed("dark")
        after = window.monitor_button.icon()

        # QIcon has no equality by color, but a real re-creation produces
        # a new QIcon object distinct from the one built at construction.
        assert before.cacheKey() != after.cacheKey()

    def test_changing_theme_refreshes_an_already_open_monitor_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        qtbot.mouseClick(window.monitor_button, Qt.MouseButton.LeftButton)

        window._on_theme_changed("dark")

        assert window._monitor_window._current_theme == "dark"

        window._monitor_window.close()
        qtbot.waitUntil(lambda: window._monitor_window is None, timeout=2000)

    def test_changing_theme_refreshes_an_already_open_scan_window(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        qtbot.mouseClick(window.scan_button, Qt.MouseButton.LeftButton)

        window._on_theme_changed("light")

        assert window._scan_window._current_theme == "light"

        window._scan_window.close()
        qtbot.waitUntil(lambda: window._scan_window is None, timeout=2000)


# ===========================================================================
# Window geometry (remember_window_geometry) and tooltips (show_tooltips)
# ===========================================================================

class TestWindowGeometryAndTooltips:
    def test_geometry_saved_on_close_when_enabled(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("ui.remember_window_geometry", True)

        window.close()

        assert SettingsManager().get("ui.window_geometry") != ""

    def test_geometry_not_saved_on_close_when_disabled(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)
        window.settings_manager.set("ui.remember_window_geometry", False)
        window.settings_manager.save()

        window.close()

        assert SettingsManager().get("ui.window_geometry") == ""

    def test_tooltips_present_by_default(self, qtbot):
        window = LandingPage()
        qtbot.addWidget(window)

        assert window.monitor_button.toolTip() != ""
        assert window.scan_button.toolTip() != ""

    def test_tooltips_cleared_when_show_tooltips_disabled(self, qtbot):
        mgr = SettingsManager()
        mgr.set("ui.show_tooltips", False)
        mgr.save()

        window = LandingPage()
        qtbot.addWidget(window)

        assert window.monitor_button.toolTip() == ""
        assert window.scan_button.toolTip() == ""
