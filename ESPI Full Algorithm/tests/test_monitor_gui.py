"""
test_monitor_gui.py
Tests for monitor_gui.py — the PyQt6 dashboard version of monitor.py.

QT_QPA_PLATFORM is forced to "offscreen" before PyQt6 is imported, so this
suite (and CI) can run with no real display attached. Set QT_QPA_PLATFORM
yourself before running pytest if you want to watch the dashboard's windows
while debugging a failing test.

Sections covered
----------------
  SetupPage
    Defaults matching monitor.py's terminal defaults (camera, index box
    visibility, exposure/gain/gain_factor spin box validation, graph type
    choices), and the live summary label updating from every input.

  MonitorWorker
    Camera connect/disconnect lifecycle, exposure unit conversion per
    camera choice, frame_ready emitting (frame, diff) with diff=None on the
    first frame and a real diff from the second frame on, the cooperative
    stop() flag actually ending the loop, and every failure path (missing
    camera, grab failure, an unexpected exception) still reaching
    finished_cleanly exactly once.

  LiveMonitorPage
    start_monitor() wiring a worker and showing/hiding the graph canvas
    correctly per graph_type, is_running()/stop_and_wait().

  MainWindow
    Nav rail gating (Live Monitor disabled until a session starts, Setup
    disabled while one is running), and the closeEvent() confirmation guard
    for a running monitor.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton

import camera_control_inclusive as cci
import live_graphs
import monitor
import settings_manager
from monitor_gui import (
    SetupPage,
    SettingsPage,
    MonitorWorker,
    LiveMonitorPage,
    MainWindow,
    AmplificationComparisonDialog,
    _apply_clahe,
    _apply_gamma_correction,
    _apply_diff_amplification,
    _compare_amplification_methods,
    _AMPLIFICATION_METHODS,
    _apply_grayscale_conversion,
    _grayscale_numpy,
    _grayscale_pillow,
    _grayscale_opencv_hsv,
    LearnMoreDialog,
    GrayscaleComparisonDialog,
    _compare_grayscale_methods,
    _GRAYSCALE_COMPARISON_METHODS,
)


def _settings(**overrides):
    base = dict(
        exposure_s=0.05,
        gain_db=1.0,
        gain_factor=10.0,
        graph_type=None,
        n_averages=1,
        averaging_method="frame_averaging",
        diff_amplification="normalize",
        clahe_clip_limit=2.0,
        clahe_tile_grid_size=(8, 8),
        gamma=0.5,
    )
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _stop_leaked_workers(monkeypatch):
    """
    Guarantee no MonitorWorker keeps running past its test, pass or fail.

    A MonitorWorker's while loop is only paced by real camera I/O — when a
    test mocks grab_single_frame_color_with_retry() to return instantly,
    nothing throttles the loop at all. If a test raises (e.g. a failed assertion) before it
    reaches stop_and_wait(), the worker thread is left spinning as fast as
    the CPU allows, forever — this was hit for real while writing this
    suite and pinned a full CPU core indefinitely. Wrapping the
    constructor records every instance created during a test so teardown
    can always stop it, however the test got there (directly, through
    LiveMonitorPage, or through MainWindow).
    """
    created = []
    original_init = MonitorWorker.__init__

    def _tracking_init(self, *args, **kwargs):
        created.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MonitorWorker, "__init__", _tracking_init)
    yield
    for worker in created:
        if worker.isRunning():
            worker.stop()
            worker.wait(2000)


# ===========================================================================
# SetupPage
# ===========================================================================

class TestSetupPage:
    def test_default_is_webcam(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        assert page.camera_choice() == "2"

    @pytest.mark.parametrize("choice", ["1", "2", "3"])
    def test_selecting_each_choice(self, qtbot, choice):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios[choice].setChecked(True)
        assert page.camera_choice() == choice

    def test_basler_hides_index_box_and_forces_zero(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._index_spin.setValue(7)  # leftover value from a previous choice
        page._radios["1"].setChecked(True)
        assert page._index_spin.isVisible() is False
        assert page.camera_index() == 0

    @pytest.mark.parametrize("choice", ["2", "3"])
    def test_non_basler_shows_index_box(self, qtbot, choice):
        page = SetupPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._radios[choice].setChecked(True)
        assert page._index_spin.isVisible() is True

    def test_settings_defaults_match_cli_defaults(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        settings = page.settings()
        assert settings["exposure_s"] == pytest.approx(0.06)
        assert settings["gain_db"] == pytest.approx(1.0)
        assert settings["gain_factor"] == pytest.approx(10.0)
        assert settings["n_averages"] == 1
        # graph_type and diff_amplification are now in SettingsPage
        assert "graph_type" not in settings
        assert "diff_amplification" not in settings

    def test_exposure_cannot_reach_zero_or_below(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0)
        assert page.exposure_spin.value() > 0
        page.exposure_spin.setValue(-5)
        assert page.exposure_spin.value() > 0

    def test_gain_factor_cannot_reach_zero_or_below(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.gain_factor_spin.setValue(0)
        assert page.gain_factor_spin.value() > 0
        page.gain_factor_spin.setValue(-1)
        assert page.gain_factor_spin.value() > 0

    def test_gain_db_may_be_zero_or_negative(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.gain_spin.setValue(-3.0)
        assert page.settings()["gain_db"] == pytest.approx(-3.0)

    def test_summary_updates_with_camera_choice(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios["1"].setChecked(True)
        assert "Basler" in page._summary_label.text()
        assert "index" not in page._summary_label.text()

    def test_summary_shows_index_for_non_basler(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios["3"].setChecked(True)
        page._index_spin.setValue(2)
        assert "index 2" in page._summary_label.text()

    def test_summary_updates_with_settings(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0.02)
        assert "0.02" in page._summary_label.text()


class TestSetupPageLockedByUseLastSettingsAsDefault:
    """
    While "Use Last Settings as Default" is on (set from espi_app's
    Settings dialog, bridged into this shared settings file), camera,
    index, exposure, gain, and gain_factor are auto-managed from whatever
    was actually last used to start a monitor session — not something to
    type in by hand — so those fields are disabled. n_averages is not a
    tracked default and stays editable either way.
    """

    def test_fields_enabled_when_flag_is_off(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": False,
        })

        page = SetupPage()
        qtbot.addWidget(page)

        assert page._radios["2"].isEnabled() is True
        assert page._index_spin.isEnabled() is True
        assert page.exposure_spin.isEnabled() is True
        assert page.gain_spin.isEnabled() is True
        assert page.gain_factor_spin.isEnabled() is True
        assert page.n_averages_spin.isEnabled() is True

    def test_fields_disabled_when_flag_is_on(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": True,
        })

        page = SetupPage()
        qtbot.addWidget(page)

        for choice in ("1", "2", "3"):
            assert page._radios[choice].isEnabled() is False
        assert page._index_spin.isEnabled() is False
        assert page.exposure_spin.isEnabled() is False
        assert page.gain_spin.isEnabled() is False
        assert page.gain_factor_spin.isEnabled() is False
        # Not a tracked default — always stays editable.
        assert page.n_averages_spin.isEnabled() is True


# ===========================================================================
# SettingsPage
# ===========================================================================

class TestSettingsPage:
    def test_grayscale_backend_choices_include_opencv_split_not_hsv(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        backend_values = [
            settings_page._backend_combo.itemData(i)
            for i in range(settings_page._backend_combo.count())
        ]
        assert "opencv_split" in backend_values
        assert "opencv_hsv" not in backend_values

    def test_default_averaging_method_is_averaged_differences(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page.averaging_method() == "averaged_differences"

    def test_can_select_frame_averaging(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._averaging_radios["frame_averaging"].setChecked(True)
        assert settings_page.averaging_method() == "frame_averaging"

    def test_can_select_averaged_differences(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._averaging_radios["averaged_differences"].setChecked(True)
        assert settings_page.averaging_method() == "averaged_differences"

    @pytest.mark.parametrize("choice,expected", [
        ("1", "histogram"),
        ("2", "log_histogram"),
        ("3", "3d"),
        ("4", None),
    ])
    def test_graph_type_choices(self, qtbot, choice, expected):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._graph_radios[choice].setChecked(True)
        assert settings_page.graph_type() == expected

    def test_default_graph_type_is_none(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page.graph_type() is None

    @pytest.mark.parametrize("choice", ["none", "normalize", "gain_factor", "clahe", "gamma"])
    def test_diff_amplification_choices(self, qtbot, choice):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._amp_radios[choice].setChecked(True)
        assert settings_page.diff_amplification() == choice

    def test_default_diff_amplification_is_gain_factor(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page.diff_amplification() == "gain_factor"

    def test_clahe_param_defaults(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page.clahe_clip_limit() == pytest.approx(2.0)
        assert settings_page.clahe_tile_grid_size() == (8, 8)

    def test_clahe_clip_limit_range(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page._clahe_clip_spin.minimum() == pytest.approx(0.5)
        assert settings_page._clahe_clip_spin.maximum() == pytest.approx(10.0)

    def test_gamma_param_default(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page.gamma_value() == pytest.approx(0.5)

    def test_gamma_range(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page._gamma_spin.minimum() == pytest.approx(0.1)
        assert settings_page._gamma_spin.maximum() == pytest.approx(3.0)

    def test_clahe_and_gamma_params_hidden_by_default(self, qtbot):
        """Default amplification is now gain_factor, so neither param group should show."""
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert settings_page._clahe_clip_spin.isVisible() is False
        assert settings_page._gamma_spin.isVisible() is False
        # Regression: the "x" separator label between the tile row/col spin
        # boxes was left out of the visibility wiring and stayed floating in
        # the layout even when CLAHE wasn't selected.
        assert settings_page._tile_x_label.isVisible() is False

    def test_clahe_params_visible_only_when_clahe_selected(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page.show()
        qtbot.waitExposed(settings_page)
        settings_page._amp_radios["clahe"].setChecked(True)
        assert settings_page._clahe_clip_spin.isVisible() is True
        assert settings_page._tile_rows_spin.isVisible() is True
        assert settings_page._gamma_spin.isVisible() is False

    def test_gamma_param_visible_only_when_gamma_selected(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page.show()
        qtbot.waitExposed(settings_page)
        settings_page._amp_radios["gamma"].setChecked(True)
        assert settings_page._gamma_spin.isVisible() is True
        assert settings_page._clahe_clip_spin.isVisible() is False

    def test_tooltips_are_set_on_averaging_radios(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        for choice, radio in settings_page._averaging_radios.items():
            assert len(radio.toolTip()) > 0

    def test_tooltips_are_set_on_graph_radios(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        for choice, radio in settings_page._graph_radios.items():
            assert len(radio.toolTip()) > 0

    def test_tooltips_are_set_on_amplification_radios(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        for choice, radio in settings_page._amp_radios.items():
            assert len(radio.toolTip()) > 0


# ===========================================================================
# Learn More buttons
# ===========================================================================

class _FakeLearnMoreDialog:
    """Stands in for LearnMoreDialog so tests never open a real modal popup."""
    created = []

    def __init__(self, title, html_content, parent=None):
        _FakeLearnMoreDialog.created.append((title, html_content))

    def exec(self):
        return None


class TestLearnMoreButtons:
    """
    Each processing method group (grayscale conversion, frame averaging,
    intensity graph, difference amplification) gets a Learn More button that
    opens a plain language explanation, so someone unfamiliar with these
    algorithms is not stuck guessing what a radio button label means.
    """

    @pytest.fixture(autouse=True)
    def _fake_dialog(self, monkeypatch):
        _FakeLearnMoreDialog.created = []
        monkeypatch.setattr("monitor_gui.LearnMoreDialog", _FakeLearnMoreDialog)
        yield

    def test_every_group_has_a_learn_more_button(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        assert isinstance(settings_page._grayscale_learn_more_button, QPushButton)
        assert isinstance(settings_page._averaging_learn_more_button, QPushButton)
        assert isinstance(settings_page._graph_learn_more_button, QPushButton)
        assert isinstance(settings_page._amplification_learn_more_button, QPushButton)

    def test_grayscale_learn_more_mentions_its_own_options(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._grayscale_learn_more_button.click()
        title, html = _FakeLearnMoreDialog.created[0]
        assert "grayscale" in title.lower()
        for keyword in ("Full-RGB", "channel", "NumPy", "Pillow"):
            assert keyword in html

    def test_averaging_learn_more_mentions_its_own_options(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._averaging_learn_more_button.click()
        title, html = _FakeLearnMoreDialog.created[0]
        assert "averaging" in title.lower()
        for keyword in ("Average of differences", "Difference of averages", "speckle"):
            assert keyword in html

    def test_graph_learn_more_mentions_its_own_options(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._graph_learn_more_button.click()
        title, html = _FakeLearnMoreDialog.created[0]
        assert "graph" in title.lower()
        for keyword in ("Histogram", "Log histogram", "3D surface"):
            assert keyword in html

    def test_amplification_learn_more_mentions_its_own_options(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._amplification_learn_more_button.click()
        title, html = _FakeLearnMoreDialog.created[0]
        assert "amplification" in title.lower()
        for keyword in ("Normalize", "Gain factor", "CLAHE", "Gamma", "clip limit"):
            assert keyword in html

    def test_each_button_click_opens_exactly_one_dialog(self, qtbot):
        setup = SetupPage()
        settings_page = SettingsPage(setup)
        qtbot.addWidget(settings_page)
        settings_page._amplification_learn_more_button.click()
        assert len(_FakeLearnMoreDialog.created) == 1


class TestLearnMoreDialog:
    def test_shows_the_given_html_content(self, qtbot):
        dialog = LearnMoreDialog("Test Title", "<p>hello world</p>")
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "Test Title"
        assert "hello world" in dialog.browser.toPlainText()


# ===========================================================================
# Single-channel grayscale extraction backends (pure functions, no Qt needed)
# ===========================================================================

@pytest.fixture
def bgr_frame_distinct_channels():
    """A 20x20 BGR frame where each channel has a different, known value."""
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    frame[:, :, 0] = 100  # Blue
    frame[:, :, 1] = 150  # Green
    frame[:, :, 2] = 200  # Red
    return frame


class TestGrayscaleOpencvSplit:
    """
    _grayscale_opencv_hsv uses HSV-based hue masking to extract single-channel
    intensity. It isolates pixels of a specific hue and returns their brightness,
    unlike raw channel extraction. These tests verify the backend returns a
    continuous intensity value for every pixel, matching _grayscale_numpy exactly.
    """

    @pytest.mark.parametrize("color_code,expected_value", [("B", 100), ("G", 150), ("R", 200)])
    def test_extracts_correct_channel_value(self, bgr_frame_distinct_channels, color_code, expected_value):
        result = _grayscale_opencv_hsv(bgr_frame_distinct_channels, color_code)
        assert np.all(result == expected_value)

    @pytest.mark.parametrize("color_code", ["B", "G", "R"])
    def test_matches_numpy_backend_exactly(self, gray_100x100, color_code):
        # Build a BGR frame out of gray_100x100 so every channel has varied,
        # non-uniform values instead of one flat number per channel.
        rng = np.random.default_rng(2)
        bgr = rng.integers(0, 256, size=(100, 100, 3), dtype=np.uint8)

        via_opencv = _grayscale_opencv_hsv(bgr, color_code)
        via_numpy = _grayscale_numpy(bgr, color_code)

        assert np.array_equal(via_opencv, via_numpy)

    def test_output_is_uint8_2d(self, bgr_frame_distinct_channels):
        result = _grayscale_opencv_hsv(bgr_frame_distinct_channels, "R")
        assert result.dtype == np.uint8
        assert result.shape == bgr_frame_distinct_channels.shape[:2]

    def test_no_pixels_are_zeroed_out(self):
        """
        The old HSV-masking implementation zeroed any pixel whose hue fell
        outside a narrow band. A uniformly low-saturation frame (all gray,
        no dominant hue) used to come back mostly black; it must not anymore.
        """
        low_saturation_frame = np.full((20, 20, 3), 180, dtype=np.uint8)
        result = _grayscale_opencv_hsv(low_saturation_frame, "R")
        assert np.all(result == 180)


class TestApplyGrayscaleConversionDispatch:
    def test_dispatches_to_opencv_split_backend(self, bgr_frame_distinct_channels):
        result = _apply_grayscale_conversion(
            bgr_frame_distinct_channels, method="single_channel",
            color="G", backend="opencv_split",
        )
        assert np.all(result == 150)


class TestCompareGrayscaleMethods:
    """
    Backs the Compare Grayscale Methods button: runs Standard Full-RGB and
    all three single-channel backends on the same raw frame, so their
    effect can be compared side by side, the same way
    _compare_amplification_methods already does for amplification.
    """

    def _mostly_red_frame(self):
        frame = np.zeros((30, 30, 3), dtype=np.uint8)
        frame[:, :, 2] = 200  # Red (BGR index 2)
        frame[:, :, 1] = 10
        frame[:, :, 0] = 10
        return frame

    def test_returns_an_entry_for_every_method(self):
        results = _compare_grayscale_methods(self._mostly_red_frame(), color="R")
        assert set(results.keys()) == set(_GRAYSCALE_COMPARISON_METHODS)

    def test_each_entry_has_image_time_and_brightness(self):
        results = _compare_grayscale_methods(self._mostly_red_frame(), color="R")
        for method, (image, elapsed, brightness) in results.items():
            assert image.shape == (30, 30)
            assert image.dtype == np.uint8
            assert elapsed >= 0
            assert brightness >= 0

    def test_single_channel_red_is_brighter_than_standard_on_a_red_frame(self):
        """
        This is the exact scenario that exposed the color pipeline bug:
        on a genuinely red frame, extracting the red channel directly
        should read much brighter than the standard luminosity blend.
        """
        results = _compare_grayscale_methods(self._mostly_red_frame(), color="R")
        _, _, standard_brightness = results["standard"]
        for backend in ("numpy", "pillow", "opencv_split"):
            _, _, backend_brightness = results[backend]
            assert backend_brightness > standard_brightness + 100

    def test_all_three_backends_agree_with_each_other(self):
        results = _compare_grayscale_methods(self._mostly_red_frame(), color="R")
        numpy_image, _, _ = results["numpy"]
        pillow_image, _, _ = results["pillow"]
        opencv_image, _, _ = results["opencv_split"]
        assert np.array_equal(numpy_image, pillow_image)
        assert np.array_equal(numpy_image, opencv_image)


class TestGrayscaleComparisonDialog:
    def test_builds_one_entry_per_method(self, qtbot):
        frame = np.zeros((30, 30, 3), dtype=np.uint8)
        frame[:, :, 2] = 200
        dialog = GrayscaleComparisonDialog(frame, color="R")
        qtbot.addWidget(dialog)
        labels = dialog.findChildren(QLabel)
        assert len(labels) >= 2 * len(_GRAYSCALE_COMPARISON_METHODS)


class TestApplyClahe:
    def test_output_is_uint8_same_shape(self, gray_100x100):
        result = _apply_clahe(gray_100x100, clip_limit=2.0, tile_grid_size=(8, 8))
        assert result.dtype == np.uint8
        assert result.shape == gray_100x100.shape

    def test_increases_contrast_on_low_contrast_image(self):
        # Two flat bands with only a small intensity gap between them
        low_contrast = np.zeros((40, 40), dtype=np.uint8)
        low_contrast[:20, :] = 100
        low_contrast[20:, :] = 110

        result = _apply_clahe(low_contrast, clip_limit=2.0, tile_grid_size=(4, 4))

        assert result.std() > low_contrast.std()

    def test_uniform_image_stays_uniform(self, uniform_gray):
        result = _apply_clahe(uniform_gray, clip_limit=2.0, tile_grid_size=(8, 8))
        # CLAHE has nothing to equalize on a flat field
        assert np.all(result == result[0, 0])

    def test_higher_clip_limit_is_accepted(self, gray_100x100):
        # Should not raise across the full documented range
        _apply_clahe(gray_100x100, clip_limit=0.5, tile_grid_size=(8, 8))
        _apply_clahe(gray_100x100, clip_limit=10.0, tile_grid_size=(8, 8))


class TestApplyGammaCorrection:
    def test_output_is_uint8_same_shape(self, gray_100x100):
        result = _apply_gamma_correction(gray_100x100, gamma=0.5)
        assert result.dtype == np.uint8
        assert result.shape == gray_100x100.shape

    def test_gamma_below_one_brightens_midtones(self):
        midtone = np.full((10, 10), 128, dtype=np.uint8)
        result = _apply_gamma_correction(midtone, gamma=0.5)
        assert result[0, 0] > midtone[0, 0]

    def test_gamma_above_one_darkens_midtones(self):
        midtone = np.full((10, 10), 128, dtype=np.uint8)
        result = _apply_gamma_correction(midtone, gamma=2.0)
        assert result[0, 0] < midtone[0, 0]

    def test_gamma_one_is_identity(self, gray_100x100):
        result = _apply_gamma_correction(gray_100x100, gamma=1.0)
        assert np.array_equal(result, gray_100x100)

    def test_black_and_white_pixels_unaffected(self, black_image, white_image):
        assert np.all(_apply_gamma_correction(black_image, gamma=0.5) == 0)
        assert np.all(_apply_gamma_correction(white_image, gamma=0.5) == 255)


class TestApplyDiffAmplificationDispatch:
    def test_none_returns_raw_diff_unchanged(self, gray_100x100):
        result = _apply_diff_amplification(
            cci, gray_100x100, "none", gain_factor=10.0,
        )
        assert np.array_equal(result, gray_100x100)

    def test_gain_factor_uses_convert_scale_abs(self, uniform_gray, monkeypatch):
        calls = []
        original = cv2.convertScaleAbs

        def _spy(src, alpha=1.0):
            calls.append(alpha)
            return original(src, alpha=alpha)

        monkeypatch.setattr(cv2, "convertScaleAbs", _spy)
        _apply_diff_amplification(cci, uniform_gray, "gain_factor", gain_factor=5.0)
        assert calls == [5.0]

    def test_normalize_delegates_to_cam_lib_amplify_difference(self, gray_100x100, monkeypatch):
        received = []
        monkeypatch.setattr(cci, "amplify_difference", lambda x: received.append(x) or x)
        _apply_diff_amplification(cci, gray_100x100, "normalize", gain_factor=1.0)
        assert len(received) == 1
        assert np.array_equal(received[0], gray_100x100)

    def test_clahe_dispatch_matches_direct_call(self, gray_100x100):
        via_dispatch = _apply_diff_amplification(
            cci, gray_100x100, "clahe", gain_factor=1.0,
            clahe_clip_limit=3.0, clahe_tile_grid_size=(4, 4),
        )
        direct = _apply_clahe(gray_100x100, clip_limit=3.0, tile_grid_size=(4, 4))
        assert np.array_equal(via_dispatch, direct)

    def test_gamma_dispatch_matches_direct_call(self, gray_100x100):
        via_dispatch = _apply_diff_amplification(
            cci, gray_100x100, "gamma", gain_factor=1.0, gamma=0.4,
        )
        direct = _apply_gamma_correction(gray_100x100, gamma=0.4)
        assert np.array_equal(via_dispatch, direct)


class TestCompareAmplificationMethods:
    def test_returns_an_entry_for_every_method(self, gray_100x100):
        results = _compare_amplification_methods(cci, gray_100x100, gain_factor=10.0)
        assert set(results.keys()) == set(_AMPLIFICATION_METHODS)

    def test_each_entry_has_image_time_and_contrast(self, gray_100x100):
        results = _compare_amplification_methods(cci, gray_100x100, gain_factor=10.0)
        for method, (image, elapsed, contrast) in results.items():
            assert image.shape == gray_100x100.shape
            assert image.dtype == np.uint8
            assert elapsed >= 0
            assert contrast >= 0


class TestAmplificationComparisonDialog:
    def test_builds_one_entry_per_method(self, qtbot, gray_100x100):
        dialog = AmplificationComparisonDialog(
            cci, gray_100x100, gain_factor=10.0,
            clahe_clip_limit=2.0, clahe_tile_grid_size=(8, 8), gamma=0.5,
        )
        qtbot.addWidget(dialog)
        # One image label + one caption label per method, plus the Close button.
        labels = dialog.findChildren(QLabel)
        assert len(labels) >= 2 * len(_AMPLIFICATION_METHODS)


# ===========================================================================
# MonitorWorker
# ===========================================================================

class TestMonitorWorker:
    def test_frame_ready_diff_none_on_first_frame(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(diff))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        assert received[0] is None

    def test_raw_frame_ready_emits_the_pre_grayscale_frame(self, qtbot, monkeypatch):
        mock_camera = object()
        red_frame = np.zeros((50, 50, 3), dtype=np.uint8)
        red_frame[:, :, 2] = 200
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: red_frame.copy())
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        received = []
        worker.raw_frame_ready.connect(lambda frame: received.append(frame))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # The raw frame must still be the real (H, W, 3) BGR data, not
        # whatever _apply_grayscale_conversion later reduces it to.
        assert received[0].ndim == 3
        assert received[0].shape[2] == 3
        assert np.all(received[0][:, :, 2] == 200)

    def test_frame_ready_computes_diff_from_second_frame_on(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        mock_camera = object()
        frames = [gray_100x100, gray_100x100_b, gray_100x100_b]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else gray_100x100_b)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(diff))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 2, timeout=2000)
        worker.stop()
        worker.wait(2000)

        assert received[0] is None
        assert received[1] is not None
        assert isinstance(received[1], np.ndarray)

    def test_exposure_converted_with_log2_for_usb_camera(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        received_exposure = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(
            cci, "set_exposure_manual",
            lambda cam, value: received_exposure.append(value),
        )
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings(exposure_s=0.06))
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.frame_ready.connect(lambda *_: worker.stop())
        worker.start()
        finished_blocker.wait()

        assert received_exposure[0] == pytest.approx(np.log2(0.06))

    def test_disconnect_called_exactly_once_on_stop(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        disconnect_calls = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.frame_ready.connect(lambda *_: worker.stop())
        worker.start()
        finished_blocker.wait()

        assert disconnect_calls == [mock_camera]

    def test_missing_camera_emits_error_and_still_finishes(self, qtbot, monkeypatch):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: None)
        disconnect_calls = []
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert disconnect_calls == []  # never connected, so never disconnected

    def test_grab_failure_emits_error_and_finishes(self, qtbot, monkeypatch):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: None)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "grab" in error_blocker.args[0].lower()

    def test_unexpected_exception_emits_error_and_still_disconnects(self, qtbot, monkeypatch):
        mock_camera = object()
        disconnect_calls = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)

        def _boom(cam, **kwargs):
            raise RuntimeError("camera unplugged")

        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", _boom)
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "camera unplugged" in error_blocker.args[0]
        assert disconnect_calls == [mock_camera]


# ===========================================================================
# Averaging Strategies
# ===========================================================================

class TestAveragingStrategies:
    """
    Test both averaging methods: 'frame_averaging' (current) and
    'averaged_differences' (new). Both should be available and work correctly.
    """

    def test_frame_averaging_averages_raw_frames_then_subtracts(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        """
        Frame averaging (current method):
        1. Collect n_averages raw frames
        2. Average them together
        3. Subtract from previous average
        """
        mock_camera = object()
        frame_a1 = np.full((100, 100), 100, dtype=np.uint8)
        frame_a2 = np.full((100, 100), 102, dtype=np.uint8)
        frame_b1 = np.full((100, 100), 120, dtype=np.uint8)
        frame_b2 = np.full((100, 100), 122, dtype=np.uint8)

        frames = [frame_a1, frame_a2, frame_b1, frame_b2, frame_b1, frame_b2]

        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else None
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)
        monkeypatch.setattr(cci, "substract_frames", lambda a, b: cv2.absdiff(a, b))
        monkeypatch.setattr(cci, "amplify_difference", lambda x: x)

        worker = MonitorWorker("2", 0, _settings(n_averages=2, diff_amplification="none"))
        received_frames = []
        received_diffs = []
        worker.frame_ready.connect(
            lambda frame, diff: (received_frames.append(frame), received_diffs.append(diff))
        )

        worker.start()
        qtbot.waitUntil(lambda: len(received_frames) >= 2, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # First averaged frame: (100 + 102) / 2 = 101
        assert np.allclose(received_frames[0], 101, atol=1)
        # First diff should be None (no previous frame)
        assert received_diffs[0] is None
        # Second averaged frame: (120 + 122) / 2 = 121
        assert np.allclose(received_frames[1], 121, atol=1)
        # Second diff should be |101 - 121| = 20
        assert received_diffs[1] is not None

    def test_averaged_differences_subtracts_frames_first_then_averages(
        self, qtbot, monkeypatch
    ):
        """
        Averaged differences (new method):
        1. Grab frame1, grab frame2
        2. Subtract: difference = |frame2 - frame1|
        3. Add difference to buffer
        4. Repeat until buffer has n_averages differences
        5. Average all differences together

        Verifies that:
        - Live feed emits actual raw frames (frame2 values)
        - Difference window emits averaged differences (only after n_averages ready)
        """
        mock_camera = object()
        frame_a1 = np.full((100, 100), 100, dtype=np.uint8)
        frame_a2 = np.full((100, 100), 110, dtype=np.uint8)
        frame_b1 = np.full((100, 100), 120, dtype=np.uint8)
        frame_b2 = np.full((100, 100), 130, dtype=np.uint8)
        frame_c1 = np.full((100, 100), 125, dtype=np.uint8)
        frame_c2 = np.full((100, 100), 135, dtype=np.uint8)
        frame_d1 = np.full((100, 100), 140, dtype=np.uint8)

        frames = [
            frame_a1, frame_a2,  # diff: 10
            frame_b1, frame_b2,  # diff: 10
            frame_c1, frame_c2,  # diff: 10
            frame_d1,
        ]

        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else None
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)
        monkeypatch.setattr(cci, "substract_frames", lambda a, b: cv2.absdiff(a, b))
        monkeypatch.setattr(cci, "amplify_difference", lambda x: x)

        settings = _settings(n_averages=3, averaging_method="averaged_differences", diff_amplification="none")
        worker = MonitorWorker("2", 0, settings)
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append((frame, diff)))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 3, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # Verify emissions: live feed updates every frame pair, diff updates when n_averages ready
        # received[0]: (frame_a2, None) - first pair, diff buffer has 1 difference
        # received[1]: (frame_b2, None) - second pair, diff buffer has 2 differences
        # received[2]: (frame_c2, None) - third pair, buffer full, compute averaged_diff but prev_averaged_diff is None
        # received[3]: (frame_d1 or next, computed_diff) - diff now becomes available

        assert len(received) >= 1, "Should have at least 1 emission"
        frame0, diff0 = received[0]
        assert np.allclose(frame0, 110, atol=1), f"First emission should show frame_a2 (110), got {frame0[0,0]}"
        assert diff0 is None, "First emission diff should be None"

        assert len(received) >= 3, "Should have at least 3 emissions"
        frame2, diff2 = received[2]
        assert np.allclose(frame2, 135, atol=1), f"Third emission should show frame_c2 (135), got {frame2[0,0]}"
        assert diff2 is None, "Third emission diff is still None (no previous averaged_diff for comparison)"

        # Live feed shows real frames, not differences
        for i in range(min(3, len(received))):
            frame_i, _ = received[i]
            expected_values = [110, 130, 135]  # frame_a2, frame_b2, frame_c2
            if i < len(expected_values):
                assert np.allclose(frame_i, expected_values[i], atol=1), \
                    f"Emission {i} should show frame at {expected_values[i]}, got {frame_i[0,0]}"

    @pytest.mark.parametrize("diff_amplification", ["clahe", "gamma"])
    def test_new_amplification_methods_only_affect_diff_not_live_feed(
        self, qtbot, monkeypatch, diff_amplification
    ):
        """
        CLAHE and gamma correction must only ever transform the post-averaging
        diff array (see monitor_gui.py's _apply_diff_amplification), the same
        contract normalize/gain_factor already follow. The live feed frames
        emitted alongside the diff must stay the raw averaged pixel values.
        """
        mock_camera = object()
        frame_a1 = np.full((100, 100), 100, dtype=np.uint8)
        frame_a2 = np.full((100, 100), 102, dtype=np.uint8)
        frame_b1 = np.full((100, 100), 120, dtype=np.uint8)
        frame_b2 = np.full((100, 100), 122, dtype=np.uint8)

        frames = [frame_a1, frame_a2, frame_b1, frame_b2, frame_b1, frame_b2]

        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else None
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)
        monkeypatch.setattr(cci, "substract_frames", lambda a, b: cv2.absdiff(a, b))

        worker = MonitorWorker(
            "2", 0, _settings(n_averages=2, diff_amplification=diff_amplification)
        )
        received_frames = []
        received_diffs = []
        worker.frame_ready.connect(
            lambda frame, diff: (received_frames.append(frame), received_diffs.append(diff))
        )

        worker.start()
        qtbot.waitUntil(lambda: len(received_frames) >= 2, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # Live feed is untouched by the amplification choice: still the raw averages.
        assert np.allclose(received_frames[0], 101, atol=1)
        assert np.allclose(received_frames[1], 121, atol=1)

        # Diff is available and valid from the second averaged frame on.
        assert received_diffs[0] is None
        assert received_diffs[1] is not None
        assert received_diffs[1].dtype == np.uint8
        assert received_diffs[1].shape == frame_a1.shape


# ===========================================================================
# Single-channel extraction end to end (regression for the color pipeline bug)
# ===========================================================================

class TestSingleChannelExtractionEndToEnd:
    """
    Regression coverage for a real bug: camera_control_inclusive.py's
    grab_single_frame() already reduced every color frame to standard
    greyscale before monitor_gui.py's single-channel extraction ever ran,
    so picking Red, Green, or Blue (or any backend) silently made no
    difference at all. Fixed by switching MonitorWorker to
    grab_single_frame_color(), which preserves the real BGR data. These
    tests use a genuinely mostly-red frame and check the live feed actually
    reflects the channel that was picked, not the old flattened value.
    """

    def _mostly_red_frame(self):
        frame = np.zeros((50, 50, 3), dtype=np.uint8)
        frame[:, :, 2] = 200  # Red (BGR index 2)
        frame[:, :, 1] = 10   # Green
        frame[:, :, 0] = 10   # Blue
        return frame

    @pytest.mark.parametrize("backend", ["numpy", "pillow", "opencv_split"])
    def test_red_channel_extraction_matches_the_real_red_value(
        self, qtbot, monkeypatch, backend
    ):
        mock_camera = object()
        red_frame = self._mostly_red_frame()

        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: red_frame.copy())
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        settings = _settings(
            grayscale_method="single_channel", grayscale_color="R", grayscale_backend=backend,
        )
        worker = MonitorWorker("2", 0, settings)
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(frame))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # Extracting the Red channel should recover the real value (200),
        # not the standard luminosity blend of R, G, and B (about 65).
        assert np.allclose(received[0], 200, atol=1)

    def test_standard_method_still_gives_the_luminosity_blend(self, qtbot, monkeypatch):
        """
        Sanity check for the other side of the same bug: Standard Full-RGB
        must still behave exactly as before, a real blend of all three
        channels, so this fix only changes single_channel's behavior.
        """
        mock_camera = object()
        red_frame = self._mostly_red_frame()

        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: red_frame.copy())
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        settings = _settings(grayscale_method="standard")
        worker = MonitorWorker("2", 0, settings)
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(frame))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        # 0.299*200 + 0.587*10 + 0.114*10 is about 66, nowhere near the raw
        # red value of 200. This confirms the fix did not accidentally make
        # "standard" behave like single-channel extraction too.
        assert not np.allclose(received[0], 200, atol=5)
        assert np.allclose(received[0], 66, atol=5)


# ===========================================================================
# LiveMonitorPage
# ===========================================================================

class TestLiveMonitorPage:
    def test_start_monitor_with_no_graph_hides_canvas(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.start_monitor("2", 0, _settings(graph_type=None))

        assert page._live_graph is None
        assert page._graph_canvas.isVisible() is False
        assert page.is_running() is True

        page.stop_and_wait()
        assert page.is_running() is False

    def test_start_monitor_with_histogram_shows_canvas(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.start_monitor("2", 0, _settings(graph_type="histogram"))

        assert isinstance(page._live_graph, live_graphs.LiveHistogram)
        assert page._live_graph._owns_figure is False
        assert page._graph_canvas.isVisible() is True

        page.stop_and_wait()

    def test_stop_button_disabled_until_started(self, qtbot):
        page = LiveMonitorPage()
        qtbot.addWidget(page)
        assert page.stop_button.isEnabled() is False

    def test_compare_button_disabled_until_started(self, qtbot):
        page = LiveMonitorPage()
        qtbot.addWidget(page)
        assert page.compare_button.isEnabled() is False

    def test_compare_button_enabled_once_diff_available(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        mock_camera = object()
        frames = [gray_100x100, gray_100x100_b, gray_100x100_b]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else gray_100x100_b
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings())

        qtbot.waitUntil(lambda: page.compare_button.isEnabled(), timeout=2000)

        page.stop_and_wait()

    def test_compare_button_disabled_again_after_stop(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        mock_camera = object()
        frames = [gray_100x100, gray_100x100_b, gray_100x100_b]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else gray_100x100_b
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings())
        qtbot.waitUntil(lambda: page.compare_button.isEnabled(), timeout=2000)

        page.stop_and_wait()

        assert page.compare_button.isEnabled() is False

    def test_compare_button_click_opens_comparison_dialog(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        mock_camera = object()
        frames = [gray_100x100, gray_100x100_b, gray_100x100_b]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else gray_100x100_b
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        created = []

        class _FakeDialog:
            def __init__(self, cam_lib, raw_diff, gain_factor, clip_limit, tile_grid_size, gamma, parent=None):
                created.append((cam_lib, raw_diff, gain_factor, clip_limit, tile_grid_size, gamma))

            def exec(self):
                return None

        monkeypatch.setattr("monitor_gui.AmplificationComparisonDialog", _FakeDialog)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings())
        qtbot.waitUntil(lambda: page.compare_button.isEnabled(), timeout=2000)

        page.compare_button.click()

        assert len(created) == 1
        cam_lib, raw_diff, gain_factor, clip_limit, tile_grid_size, gamma = created[0]
        assert cam_lib is cci
        assert isinstance(raw_diff, np.ndarray)
        assert gain_factor == pytest.approx(10.0)
        assert clip_limit == pytest.approx(2.0)
        assert tile_grid_size == (8, 8)
        assert gamma == pytest.approx(0.5)

        page.stop_and_wait()

    def test_compare_grayscale_button_disabled_until_started(self, qtbot):
        page = LiveMonitorPage()
        qtbot.addWidget(page)
        assert page.compare_grayscale_button.isEnabled() is False

    def test_compare_grayscale_button_enabled_once_raw_frame_available(
        self, qtbot, monkeypatch, gray_100x100
    ):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings())

        qtbot.waitUntil(lambda: page.compare_grayscale_button.isEnabled(), timeout=2000)

        page.stop_and_wait()

    def test_compare_grayscale_button_disabled_again_after_stop(
        self, qtbot, monkeypatch, gray_100x100
    ):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings())
        qtbot.waitUntil(lambda: page.compare_grayscale_button.isEnabled(), timeout=2000)

        page.stop_and_wait()

        assert page.compare_grayscale_button.isEnabled() is False

    def test_compare_grayscale_button_click_opens_comparison_dialog(
        self, qtbot, monkeypatch, gray_100x100
    ):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        created = []

        class _FakeDialog:
            def __init__(self, frame, color, parent=None):
                created.append((frame, color))

            def exec(self):
                return None

        monkeypatch.setattr("monitor_gui.GrayscaleComparisonDialog", _FakeDialog)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.start_monitor("2", 0, _settings(grayscale_color="G"))
        qtbot.waitUntil(lambda: page.compare_grayscale_button.isEnabled(), timeout=2000)

        page.compare_grayscale_button.click()

        assert len(created) == 1
        frame, color = created[0]
        assert isinstance(frame, np.ndarray)
        assert color == "G"

        page.stop_and_wait()


# ===========================================================================
# MainWindow
# ===========================================================================

class TestMainWindow:
    def test_live_monitor_nav_disabled_at_startup(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert not (window._nav.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)

    def test_starting_monitor_enables_live_monitor_and_disables_setup(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        assert window._nav.item(1).flags() & Qt.ItemFlag.ItemIsEnabled
        assert not (window._nav.item(0).flags() & Qt.ItemFlag.ItemIsEnabled)
        assert window._nav.currentRow() == 1

        window.live_monitor_page.stop_and_wait()

    def test_starting_monitor_moves_focus_onto_nav_rail(self, qtbot, monkeypatch, gray_100x100):
        """
        Regression test: currentRow() being 1 and item(1).isSelected() being
        True are not enough on their own. Qt style sheets can render
        ::item:selected differently depending on whether the QListWidget
        itself is the actually focused ("active") widget; setCurrentRow()
        changes which row is current and selected, but does not, on its
        own, move keyboard focus onto the list. Without focus actually
        landing on the nav rail, the Live Monitor row's highlight silently
        failed to show on a real desktop even though every other check
        (currentRow, isSelected) reported the expected state.

        This checks that setFocus() is actually called on the nav rail,
        rather than checking hasFocus()/isActiveWindow() afterward: those
        never report True inside this test harness even for a bare
        QMainWindow with nothing else going on (confirmed directly, outside
        this suite, before writing this test this way), since window
        activation depends on real OS-level focus events the offscreen
        platform doesn't simulate under pytest-qt. Calling setFocus() was
        confirmed separately, in a standalone script outside pytest, to
        actually produce hasFocus() == True end to end.
        """
        mock_camera = object()
        # Bounded frame supply (a real grab loop, then None) rather than an
        # endless lambda: if the assertion below fails, as it will before
        # the fix lands, the worker must still stop itself on its own after
        # a couple of grabs. An endless mock plus a failed assertion means
        # stop_and_wait() below never runs, leaving an unthrottled
        # background thread flooding the main thread with queued signals
        # forever, exactly the CPU-pinning hazard _stop_leaked_workers'
        # docstring warns about.
        frames = [gray_100x100, gray_100x100]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else None
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)

        focus_calls = []
        original_set_focus = window._nav.setFocus
        monkeypatch.setattr(window._nav, "setFocus", lambda *a, **k: (focus_calls.append(1), original_set_focus(*a, **k)))

        try:
            window._start_monitor()
            assert focus_calls, (
                "MainWindow._start_monitor() never calls self._nav.setFocus(). "
                "Without it, the Live Monitor row's selected highlight is not "
                "guaranteed to render, since setCurrentRow() alone does not "
                "move keyboard focus onto the nav rail."
            )
        finally:
            window.live_monitor_page.stop_and_wait()

    def test_stopping_monitor_moves_focus_back_onto_nav_rail(self, qtbot, monkeypatch, gray_100x100):
        """Same as above, for _on_monitor_stopped() moving focus back to Setup."""
        mock_camera = object()
        frames = [gray_100x100, gray_100x100]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(
            cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: frames.pop(0) if frames else None
        )
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()
        window.live_monitor_page.stop_and_wait()

        focus_calls = []
        original_set_focus = window._nav.setFocus
        monkeypatch.setattr(window._nav, "setFocus", lambda *a, **k: (focus_calls.append(1), original_set_focus(*a, **k)))

        window._on_monitor_stopped()

        assert focus_calls, (
            "MainWindow._on_monitor_stopped() never calls self._nav.setFocus()."
        )

    def test_starting_monitor_switches_stack_to_live_monitor_page(self, qtbot, monkeypatch, gray_100x100):
        """
        Regression test: verify that starting monitor actually switches the stacked widget
        to show the Live Monitor page (index 1), not just the nav rail.

        This was a bug where setCurrentRow() doesn't fire itemClicked signal,
        so the stack wouldn't switch even though the nav was updated.
        """
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)

        # Initial state: Setup page (index 0)
        assert window._stack.currentIndex() == 0

        window._start_monitor()

        # After start: should switch to Live Monitor page (index 1)
        assert window._stack.currentIndex() == 1, "Stack should show Live Monitor page (index 1) after starting monitor"

        window.live_monitor_page.stop_and_wait()

    def test_stopping_monitor_switches_stack_back_to_setup_page(self, qtbot, monkeypatch, gray_100x100):
        """
        Regression test: verify that stopping monitor switches the stacked widget
        back to the Setup page (index 0).
        """
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        # Verify we're on Live Monitor page
        assert window._stack.currentIndex() == 1

        window.live_monitor_page.stop_and_wait()
        qtbot.waitUntil(lambda: window._stack.currentIndex() == 0, timeout=2000)

        # After stop: should switch back to Setup page (index 0)
        assert window._stack.currentIndex() == 0, "Stack should show Setup page (index 0) after stopping monitor"

    def test_close_event_ignored_when_user_declines_to_stop(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        event = MagicMock()
        with patch(
            "monitor_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        assert window.live_monitor_page.is_running() is True

        window.live_monitor_page.stop_and_wait()

    def test_close_event_stops_worker_when_user_confirms(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame_color_with_retry", lambda cam, **kwargs: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        event = MagicMock()
        with patch(
            "monitor_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.closeEvent(event)

        event.accept.assert_called_once()
        assert window.live_monitor_page.is_running() is False

    def test_settings_navigation_to_and_from_setup(self, qtbot):
        """Test that Settings page works and navigation back to Setup works."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        qtbot.waitExposed(window)

        # Initial state: Setup page (index 0)
        assert window._stack.currentIndex() == 0, "Should start on Setup page (index 0)"
        assert window._nav.currentRow() == 0, "Nav should show Setup selected (row 0)"

        # Click Settings button and wait for stack to update
        with qtbot.waitSignal(window._stack.currentChanged, timeout=2000):
            window.settings_button.click()

        # Verify Settings page is shown (nav currentRow stays at 0 since Settings is not a nav item)
        assert window._stack.currentIndex() == 2, "Should show Settings page (index 2)"
        assert window._nav.currentRow() == 0, "Nav currentRow stays at Setup while Settings page is shown"

        # Click Setup item in nav rail - itemClicked always navigates regardless of currentRow
        with qtbot.waitSignal(window._stack.currentChanged, timeout=2000):
            window._nav.itemClicked.emit(window._nav.item(0))

        # Verify we're back on Setup page
        assert window._stack.currentIndex() == 0, "Should switch back to Setup page (index 0)"
        assert window._nav.currentRow() == 0, "Nav should show Setup selected (row 0)"

    def test_close_event_closes_immediately_when_nothing_running(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        event = MagicMock()
        window.closeEvent(event)


# ===========================================================================
# Auto-save "last used settings" as the new default (gated by
# use_last_settings_as_default, bridged from espi_app)
# ===========================================================================

class TestStartMonitorSavesLastUsedSettings:
    """
    Tests _save_last_used_settings_if_enabled() directly, rather than
    through _start_monitor() + a real MonitorWorker QThread: starting a
    real worker (even a fully-mocked one) ties these tests to this
    environment's pre-existing QThread start/stop issues (see the "Fix
    hanging worker-stop tests" follow-up task), which have nothing to do
    with the settings-saving logic actually being tested here.
    """

    def test_saves_defaults_and_last_used_dashboard_when_flag_is_on(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": True,
        })

        window = MainWindow()
        qtbot.addWidget(window)
        window.setup_page._radios["3"].setChecked(True)
        window.setup_page.exposure_spin.setValue(0.08)
        window.setup_page.gain_spin.setValue(4.5)
        window.setup_page.gain_factor_spin.setValue(15.0)

        window._save_last_used_settings_if_enabled(
            window.setup_page.camera_choice(), window.setup_page.settings()
        )

        saved = settings_manager.load_settings()
        assert saved["default_camera_choice"] == "3"
        assert saved["monitor_default_exposure"] == pytest.approx(0.08)
        assert saved["monitor_default_gain"] == pytest.approx(4.5)
        assert saved["monitor_default_gain_factor"] == pytest.approx(15.0)
        assert saved["last_used_dashboard"] == "monitor"

    def test_does_not_save_defaults_when_flag_is_off(self, qtbot):
        settings_manager.save_settings({
            **settings_manager.DEFAULT_SETTINGS,
            "use_last_settings_as_default": False,
            "monitor_default_exposure": 0.06,
        })

        window = MainWindow()
        qtbot.addWidget(window)
        window.setup_page.exposure_spin.setValue(0.08)

        window._save_last_used_settings_if_enabled(
            window.setup_page.camera_choice(), window.setup_page.settings()
        )

        saved = settings_manager.load_settings()
        assert saved["monitor_default_exposure"] == pytest.approx(0.06)
        assert saved.get("last_used_dashboard") != "monitor"
