"""
test_monitor_gui.py
Tests for monitor_gui.py — the PyQt6 wizard version of monitor.py.

QT_QPA_PLATFORM is forced to "offscreen" before PyQt6 is imported, so this
suite (and CI) can run with no real display attached. Set QT_QPA_PLATFORM
yourself before running pytest if you want to watch the wizard's windows
while debugging a failing test.

Sections covered
----------------
  CameraPage
    Default selection, each camera choice, and the camera index box only
    being shown for non Basler cameras (mirrors TestChooseCameraIndex in
    test_monitor.py).

  SettingsPage
    Defaults matching choose_camera_settings()'s defaults, the exposure and
    gain_factor spin boxes refusing to go to or below 0 (the GUI's
    equivalent of ask_positive_float()'s retry loop), gain_db allowing 0 or
    negative values, and each graph type choice.

  ConfirmPage
    Summary text shows an index only for non Basler cameras, matching
    TestConfirmSettings in test_monitor.py.

  MonitorWizard
    Clicking through all three pages calls monitor.launch_monitor() with
    the exact camera_choice, camera_index, and settings collected from the
    pages, and cancelling the wizard never calls it.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWizard

import monitor
from monitor_gui import CameraPage, SettingsPage, ConfirmPage, MonitorWizard


# ===========================================================================
# CameraPage
# ===========================================================================

class TestCameraPage:
    def test_default_is_webcam(self, qtbot):
        page = CameraPage()
        qtbot.addWidget(page)
        assert page.camera_choice() == "2"

    @pytest.mark.parametrize("choice", ["1", "2", "3"])
    def test_selecting_each_choice(self, qtbot, choice):
        page = CameraPage()
        qtbot.addWidget(page)
        page._radios[choice].setChecked(True)
        assert page.camera_choice() == choice

    def test_basler_hides_index_box_and_forces_zero(self, qtbot):
        page = CameraPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._index_spin.setValue(7)  # leftover value from a previous choice
        page._radios["1"].setChecked(True)
        assert page._index_spin.isVisible() is False
        assert page.camera_index() == 0

    @pytest.mark.parametrize("choice", ["2", "3"])
    def test_non_basler_shows_index_box(self, qtbot, choice):
        page = CameraPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._radios[choice].setChecked(True)
        assert page._index_spin.isVisible() is True

    def test_webcam_index_defaults_to_zero(self, qtbot):
        page = CameraPage()
        qtbot.addWidget(page)
        page._radios["2"].setChecked(True)
        assert page.camera_index() == 0

    def test_typed_index_is_returned(self, qtbot):
        page = CameraPage()
        qtbot.addWidget(page)
        page._radios["3"].setChecked(True)
        page._index_spin.setValue(2)
        assert page.camera_index() == 2


# ===========================================================================
# SettingsPage
# ===========================================================================

class TestSettingsPage:
    def test_defaults_match_cli_defaults(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)
        settings = page.settings()
        assert settings["exposure_s"] == pytest.approx(0.06)
        assert settings["gain_db"] == pytest.approx(1.0)
        assert settings["gain_factor"] == pytest.approx(20)
        assert settings["graph_type"] is None

    def test_exposure_cannot_reach_zero_or_below(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0)
        assert page.exposure_spin.value() > 0
        page.exposure_spin.setValue(-5)
        assert page.exposure_spin.value() > 0

    def test_gain_factor_cannot_reach_zero_or_below(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)
        page.gain_factor_spin.setValue(0)
        assert page.gain_factor_spin.value() > 0
        page.gain_factor_spin.setValue(-1)
        assert page.gain_factor_spin.value() > 0

    def test_gain_db_may_be_zero_or_negative(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)
        page.gain_spin.setValue(-3.0)
        assert page.settings()["gain_db"] == pytest.approx(-3.0)
        page.gain_spin.setValue(0.0)
        assert page.settings()["gain_db"] == pytest.approx(0.0)

    @pytest.mark.parametrize("choice,expected", [
        ("1", "histogram"),
        ("2", "log_histogram"),
        ("3", "3d"),
        ("4", None),
    ])
    def test_graph_type_choices(self, qtbot, choice, expected):
        page = SettingsPage()
        qtbot.addWidget(page)
        page._graph_radios[choice].setChecked(True)
        assert page.settings()["graph_type"] == expected

    def test_typed_values(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0.05)
        page.gain_spin.setValue(2.5)
        page.gain_factor_spin.setValue(10)
        page._graph_radios["1"].setChecked(True)
        settings = page.settings()
        assert settings["exposure_s"] == pytest.approx(0.05)
        assert settings["gain_db"] == pytest.approx(2.5)
        assert settings["gain_factor"] == pytest.approx(10)
        assert settings["graph_type"] == "histogram"


# ===========================================================================
# ConfirmPage
# ===========================================================================

class TestConfirmPage:
    def test_basler_summary_does_not_show_index(self, qtbot):
        camera_page = CameraPage()
        settings_page = SettingsPage()
        confirm_page = ConfirmPage(camera_page, settings_page)
        qtbot.addWidget(camera_page)
        qtbot.addWidget(settings_page)
        qtbot.addWidget(confirm_page)

        camera_page._radios["1"].setChecked(True)
        confirm_page.initializePage()
        text = confirm_page._summary_label.text()
        assert "Basler" in text
        assert "index" not in text

    @pytest.mark.parametrize("choice,name", [
        ("2", "USB / webcam"),
        ("3", "Allied Vision"),
    ])
    def test_non_basler_summary_shows_index(self, qtbot, choice, name):
        camera_page = CameraPage()
        settings_page = SettingsPage()
        confirm_page = ConfirmPage(camera_page, settings_page)
        qtbot.addWidget(camera_page)
        qtbot.addWidget(settings_page)
        qtbot.addWidget(confirm_page)

        camera_page._radios[choice].setChecked(True)
        camera_page._index_spin.setValue(1)
        confirm_page.initializePage()
        text = confirm_page._summary_label.text()
        assert name in text
        assert "index 1" in text


# ===========================================================================
# MonitorWizard — full flow
# ===========================================================================

class TestMonitorWizard:
    def test_finishing_calls_launch_monitor_with_collected_settings(self, qtbot):
        wizard = MonitorWizard()
        qtbot.addWidget(wizard)
        wizard.show()

        wizard.camera_page._radios["1"].setChecked(True)  # Basler, no index page

        with patch.object(monitor, "launch_monitor", return_value=True) as mock_launch, \
             patch("monitor_gui.QMessageBox"):
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.FinishButton), Qt.MouseButton.LeftButton)

        mock_launch.assert_called_once()
        camera_choice, camera_index, settings = mock_launch.call_args[0]
        assert camera_choice == "1"
        assert camera_index == 0
        assert settings["exposure_s"] == pytest.approx(0.06)
        assert settings["graph_type"] is None

    def test_cancelling_never_calls_launch_monitor(self, qtbot):
        wizard = MonitorWizard()
        qtbot.addWidget(wizard)
        wizard.show()

        with patch.object(monitor, "launch_monitor") as mock_launch:
            wizard.reject()

        mock_launch.assert_not_called()

    def test_failed_launch_shows_warning_not_information(self, qtbot):
        wizard = MonitorWizard()
        qtbot.addWidget(wizard)
        wizard.show()
        wizard.camera_page._radios["1"].setChecked(True)

        with patch.object(monitor, "launch_monitor", return_value=False), \
             patch("monitor_gui.QMessageBox") as mock_box:
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.FinishButton), Qt.MouseButton.LeftButton)

        mock_box.warning.assert_called_once()
        mock_box.information.assert_not_called()

    def test_unexpected_exception_shows_critical_not_a_crash(self, qtbot):
        # Something launch_monitor() itself doesn't catch (a bug, a
        # surprise KeyError, anything) must still reach the user as a
        # dialog instead of taking down the whole application.
        wizard = MonitorWizard()
        qtbot.addWidget(wizard)
        wizard.show()
        wizard.camera_page._radios["1"].setChecked(True)

        with patch.object(monitor, "launch_monitor",
                          side_effect=RuntimeError("boom")), \
             patch("monitor_gui.QMessageBox") as mock_box:
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.NextButton), Qt.MouseButton.LeftButton)
            qtbot.mouseClick(wizard.button(QWizard.WizardButton.FinishButton), Qt.MouseButton.LeftButton)

        mock_box.critical.assert_called_once()
        mock_box.warning.assert_not_called()
        mock_box.information.assert_not_called()
