"""
test_settings_dialog.py
Tests for settings_dialog.py (SettingsPage, run_experiment_gui's Settings page).

TDD regression tests for the settings propagation bug: user changes a
setting in the Settings page, but the change never reaches disk (there was
no Save button and nothing ever called SettingsPage.save_settings()), and
SettingsPage itself never reloaded from disk when shown again, so it could
silently show stale or half-edited state.

conftest.py's autouse _isolate_settings_file fixture redirects
settings_manager to a per-test tmp_path file, so every test here starts
from a clean settings.json and never touches the real ~/.espi/settings.json.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PyQt6.QtCore import Qt

from settings_dialog import SettingsPage
import settings_manager


# ===========================================================================
# Load / save round trip (the settings_manager plumbing itself, already
# correct — these confirm the baseline before testing the UI wiring on top)
# ===========================================================================

class TestSettingsPageSaveLoadRoundTrip:
    def test_save_settings_writes_every_control_to_disk(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)

        page._grayscale_radios["single_channel"].setChecked(True)
        page._color_combo.setCurrentIndex(1)  # Green
        page._camera_radios["1"].setChecked(True)  # Basler
        page._show_gain_checkbox.setChecked(True)
        page.start_freq_spin.setValue(50.0)
        page._saved_image_checkbox.setChecked(True)

        assert page.save_settings() is True

        on_disk = settings_manager.load_settings()
        assert on_disk["grayscale_method"] == "single_channel"
        assert on_disk["grayscale_color"] == "G"
        assert on_disk["default_camera_choice"] == "1"
        assert on_disk["show_gain"] is True
        assert on_disk["default_start_freq"] == pytest.approx(50.0)
        assert on_disk["show_saved_image_after_capture"] is True

    def test_load_settings_populates_every_control_from_disk(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "grayscale_method": "single_channel",
            "grayscale_color": "B",
            "default_camera_choice": "3",
            "show_gain": True,
            "default_start_freq": 250.0,
            "show_saved_image_after_capture": True,
        })

        page = SettingsPage()
        qtbot.addWidget(page)
        page.load_settings()

        assert page._grayscale_radios["single_channel"].isChecked()
        assert page._color_combo.currentIndex() == 2  # Blue (B)
        assert page._camera_radios["3"].isChecked()
        assert page._show_gain_checkbox.isChecked()
        assert page.start_freq_spin.value() == pytest.approx(250.0)
        assert page._saved_image_checkbox.isChecked()


# ===========================================================================
# THE ACTUAL BUG: nothing ever called save_settings() or load_settings()
# ===========================================================================

class TestSettingsPagePersistenceIsWired:
    """
    Regression tests for the real reported bug: "I change a setting, go to
    Setup, and Setup still shows the old value." save_settings() and
    load_settings() worked correctly in isolation (see above), but nothing
    in the app ever called them: there was no Save button, and no
    showEvent() override, so every change the user made was thrown away
    the moment they navigated to a different page.
    """

    def test_settings_page_has_a_save_control(self, qtbot):
        """
        There must be some explicit, user-facing way to persist changes.
        Without this, save_settings() is dead code no user path ever
        reaches, which is exactly what caused the reported bug.
        """
        page = SettingsPage()
        qtbot.addWidget(page)
        assert hasattr(page, "save_button"), (
            "SettingsPage needs a Save button (page.save_button) so users "
            "have an explicit action that actually persists their changes"
        )

    def test_clicking_save_button_persists_changes_to_disk(self, qtbot):
        page = SettingsPage()
        qtbot.addWidget(page)

        page._show_gain_checkbox.setChecked(True)
        page._camera_radios["1"].setChecked(True)

        qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)

        on_disk = settings_manager.load_settings()
        assert on_disk["show_gain"] is True
        assert on_disk["default_camera_choice"] == "1"

    def test_showing_the_page_reloads_from_disk(self, qtbot):
        """
        Regression test: SettingsPage must not keep showing whatever state
        it happened to have from construction time (or a previous, unsaved
        visit) once the user navigates back to it. Simulates disk changing
        underneath the page (e.g. another part of the app, or a future
        multi-window scenario) and confirms show() picks that up, the same
        way SetupPage.reload_settings() already does for the Setup page.
        """
        page = SettingsPage()
        qtbot.addWidget(page)
        assert not page._show_gain_checkbox.isChecked()

        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "show_gain": True,
            "default_camera_choice": "3",
        })

        page.show()
        qtbot.wait(10)

        assert page._show_gain_checkbox.isChecked()
        assert page._camera_radios["3"].isChecked()


class TestSettingsPageLockedByUseLastSettingsAsDefault:
    """
    While "Use Last Settings as Default" is on (set from espi_app's
    Settings dialog, bridged into this shared settings file), camera,
    index, frequency sweep, and capture fields here are auto-managed from
    whatever was actually last used to run a Preview or Sweep — this page
    exists specifically to hand-set those defaults, so while auto-managed
    it is locked, including its own Save button. Grayscale, show-gain, and
    saved-image preferences are unrelated display/processing choices and
    stay editable either way.
    """

    def test_fields_enabled_when_flag_is_off(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": False,
        })

        page = SettingsPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.wait(10)

        assert page._camera_radios["2"].isEnabled() is True
        assert page._index_spin.isEnabled() is True
        assert page.start_freq_spin.isEnabled() is True
        assert page.end_freq_spin.isEnabled() is True
        assert page.step_spin.isEnabled() is True
        assert page.n_averages_spin.isEnabled() is True
        assert page.exposure_spin.isEnabled() is True
        assert page.gain_spin.isEnabled() is True
        assert page.gain_factor_spin.isEnabled() is True
        assert page.save_button.isEnabled() is True
        # Unrelated preferences, unaffected either way.
        assert page._show_gain_checkbox.isEnabled() is True
        assert page._saved_image_checkbox.isEnabled() is True

    def test_fields_disabled_when_flag_is_on(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": True,
        })

        page = SettingsPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.wait(10)

        for choice in ("1", "2", "3"):
            assert page._camera_radios[choice].isEnabled() is False
        assert page._index_spin.isEnabled() is False
        assert page.start_freq_spin.isEnabled() is False
        assert page.end_freq_spin.isEnabled() is False
        assert page.step_spin.isEnabled() is False
        assert page.n_averages_spin.isEnabled() is False
        assert page.exposure_spin.isEnabled() is False
        assert page.gain_spin.isEnabled() is False
        assert page.gain_factor_spin.isEnabled() is False
        assert page.save_button.isEnabled() is False
        # Unrelated preferences, unaffected either way.
        assert page._show_gain_checkbox.isEnabled() is True
        assert page._saved_image_checkbox.isEnabled() is True
