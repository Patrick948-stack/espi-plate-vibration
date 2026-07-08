"""
test_live_graphs.py
Tests for live_graphs.py (live histogram + 3D surface pixel intensity graphs).

The Agg backend is forced before matplotlib.pyplot is used anywhere in this
file, so tests never open a real GUI window (fast, works on a headless CI
runner, and does not flash windows on a developer's screen while running
the suite).

Sections covered
----------------
  LiveHistogram
    Counting correctness (np.bincount matches known pixel values), window
    lifecycle (is_open/close), and that update() after close() is a safe
    no-op instead of an error.

  LiveSurfacePlot
    Constructor validation (downsample_factor, min_interval_s), the
    redraw throttle (a second update() within min_interval_s must not
    redraw), the mesh-rebuild-only-on-shape-change optimization, and the
    same window lifecycle guarantees as LiveHistogram.

  create_live_graph()
    None/"" -> None, "histogram"/"3d" -> the right class, anything else
    raises ValueError.
"""

import sys
import os

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import live_graphs

pytestmark = pytest.mark.filterwarnings(
    "ignore:FigureCanvasAgg is non-interactive"
)


@pytest.fixture(autouse=True)
def _close_all_figures():
    """Guarantee no matplotlib figure leaks between tests, pass or fail."""
    yield
    plt.close("all")


def _frame(height=20, width=30, fill=100):
    return np.full((height, width), fill, dtype=np.uint8)


# ===========================================================================
# LiveHistogram
# ===========================================================================

class TestLiveHistogram:
    def test_starts_open(self):
        hist = live_graphs.LiveHistogram()
        assert hist.is_open() is True

    def test_update_does_not_raise(self):
        hist = live_graphs.LiveHistogram()
        hist.update(_frame())

    def test_bincount_matches_known_pixel_values(self):
        # 8x8 frame of exactly value 100 everywhere -> bar 100 should read
        # 64, every other bar should still read 0. This directly checks
        # the vectorized np.bincount counting is correct, not just that
        # update() runs without crashing.
        hist = live_graphs.LiveHistogram()
        frame = np.full((8, 8), 100, dtype=np.uint8)
        hist.update(frame)

        heights = [bar.get_height() for bar in hist._bars]
        assert heights[100] == 64
        assert heights[99] == 0
        assert heights[101] == 0
        assert sum(heights) == 64

    def test_mixed_values_counted_correctly(self):
        hist = live_graphs.LiveHistogram()
        frame = np.array([[10, 10, 10], [20, 20, 30]], dtype=np.uint8)
        hist.update(frame)

        heights = [bar.get_height() for bar in hist._bars]
        assert heights[10] == 3
        assert heights[20] == 2
        assert heights[30] == 1

    def test_second_update_replaces_not_adds(self):
        # Counts must reflect only the latest frame, not accumulate across
        # calls the way a running total would.
        hist = live_graphs.LiveHistogram()
        hist.update(np.full((4, 4), 50, dtype=np.uint8))
        hist.update(np.full((4, 4), 60, dtype=np.uint8))

        heights = [bar.get_height() for bar in hist._bars]
        assert heights[50] == 0
        assert heights[60] == 16

    def test_ylim_grows_to_fit_tallest_bar(self):
        hist = live_graphs.LiveHistogram()
        big_frame = np.full((100, 100), 5, dtype=np.uint8)  # 10,000 pixels
        hist.update(big_frame)
        assert hist.ax.get_ylim()[1] > 10_000

    def test_close_sets_is_open_false(self):
        hist = live_graphs.LiveHistogram()
        hist.close()
        assert hist.is_open() is False

    def test_update_after_close_is_a_safe_no_op(self):
        hist = live_graphs.LiveHistogram()
        hist.close()
        hist.update(_frame())  # must not raise

    def test_close_twice_is_safe(self):
        hist = live_graphs.LiveHistogram()
        hist.close()
        hist.close()  # must not raise


# ===========================================================================
# LiveSurfacePlot
# ===========================================================================

class TestLiveSurfacePlotValidation:
    def test_downsample_factor_zero_raises(self):
        with pytest.raises(ValueError):
            live_graphs.LiveSurfacePlot(downsample_factor=0)

    def test_downsample_factor_negative_raises(self):
        with pytest.raises(ValueError):
            live_graphs.LiveSurfacePlot(downsample_factor=-5)

    def test_negative_min_interval_raises(self):
        with pytest.raises(ValueError):
            live_graphs.LiveSurfacePlot(min_interval_s=-0.1)

    def test_zero_min_interval_is_allowed(self):
        # 0 means "no throttling, redraw every call" — a valid choice.
        live_graphs.LiveSurfacePlot(min_interval_s=0.0)


class TestLiveSurfacePlot:
    def test_starts_open(self):
        surf = live_graphs.LiveSurfacePlot(min_interval_s=0.0)
        assert surf.is_open() is True

    def test_update_does_not_raise(self):
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=0.0)
        surf.update(_frame(height=40, width=40))

    def test_first_update_creates_a_surface(self):
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=0.0)
        assert surf._surface is None
        surf.update(_frame(height=40, width=40))
        assert surf._surface is not None

    def test_rapid_second_update_is_throttled(self):
        # min_interval_s is huge, so the second call (effectively
        # immediately after the first) must be skipped entirely: the
        # surface object must be the exact same one as after the first
        # update, proving no redraw (remove + re-plot) happened.
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=100.0)
        surf.update(_frame(height=40, width=40, fill=10))
        surface_after_first = surf._surface

        surf.update(_frame(height=40, width=40, fill=200))
        assert surf._surface is surface_after_first

    def test_update_allowed_once_throttle_window_passes(self):
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=0.0)
        surf.update(_frame(height=40, width=40, fill=10))
        surface_after_first = surf._surface

        surf.update(_frame(height=40, width=40, fill=200))
        # min_interval_s=0.0 means every call redraws, so this must be a
        # genuinely new surface object, not the one from the first call.
        assert surf._surface is not surface_after_first

    def test_mesh_not_rebuilt_when_shape_is_unchanged(self):
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=0.0)
        surf.update(_frame(height=40, width=40))
        mesh_after_first = surf._X

        surf.update(_frame(height=40, width=40))  # same shape again
        assert surf._X is mesh_after_first

    def test_mesh_rebuilt_when_shape_changes(self):
        surf = live_graphs.LiveSurfacePlot(downsample_factor=5, min_interval_s=0.0)
        surf.update(_frame(height=40, width=40))
        mesh_after_first = surf._X

        surf.update(_frame(height=80, width=80))  # different shape
        assert surf._X is not mesh_after_first

    def test_close_sets_is_open_false(self):
        surf = live_graphs.LiveSurfacePlot(min_interval_s=0.0)
        surf.close()
        assert surf.is_open() is False

    def test_update_after_close_is_a_safe_no_op(self):
        surf = live_graphs.LiveSurfacePlot(min_interval_s=0.0)
        surf.close()
        surf.update(_frame())  # must not raise


# ===========================================================================
# create_live_graph()
# ===========================================================================

class TestCreateLiveGraph:
    def test_none_returns_none(self):
        assert live_graphs.create_live_graph(None) is None

    def test_empty_string_returns_none(self):
        assert live_graphs.create_live_graph("") is None

    def test_histogram_returns_live_histogram(self):
        graph = live_graphs.create_live_graph("histogram")
        assert isinstance(graph, live_graphs.LiveHistogram)

    def test_3d_returns_live_surface_plot(self):
        graph = live_graphs.create_live_graph("3d")
        assert isinstance(graph, live_graphs.LiveSurfacePlot)

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown graph_type"):
            live_graphs.create_live_graph("bar-chart")

    def test_error_message_lists_valid_choices(self):
        with pytest.raises(ValueError, match="histogram"):
            live_graphs.create_live_graph("nonsense")
