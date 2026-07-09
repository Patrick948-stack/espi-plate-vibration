"""
live_graphs.py
Author: Patrick Mulikuza

Live, per-frame pixel intensity graphs for the camera preview windows in
monitor.py and the capture_and_display*.py scripts.

This grew out of two exploratory scripts in Learning/graph.py (a 3D surface
plot of one saved image) and Learning/graph2.py (a histogram of one saved
image). Both of those read a file from disk and opened one blocking window
with plt.show(). Neither works for a live feed.

WHAT CHANGED TO MAKE THESE "LIVE"
----------------------------------
  * Both classes below take a numpy array directly (the frame already existent in memory) instead of a file path.
  * Both create their matplotlib figure once, then update it in place every
    call to update().
  * LiveHistogram counts pixels with numpy.bincount (implemented in C)
    instead of a Python "for pixel in image" loop. For a 1920x1200 frame
    that is the difference between a sub-millisecond count and a loop that
    could take a noticeable fraction of a second on every single frame.
  * LiveSurfacePlot is throttled to redraw a few times per second instead
    of every frame. matplotlib's 3D renderer (mplot3d) is a pure-Python,
    non-GPU-accelerated renderer that depth-sorts every quad in the surface
    on every draw — there is no way to make a full 3D surface redraw at
    full camera frame rate (15-30+ fps) in matplotlib. Throttling it is
    the honest fix: the histogram can genuinely track every frame, the 3D
    view updates at a lower but still clearly "live" rate.

A third option, LiveLogHistogram, is a dark-themed line-plot version of the
same histogram idea on a log-scale y-axis, matching the "Number of Pixels
vs Pixel Value" plot style LabVIEW produces — useful when a dominant peak
(e.g. background pixels) would otherwise flatten rarer values into an
invisible sliver on a plain linear axis.

HOW TO USE
----------
    import live_graphs

    live_graph = live_graphs.create_live_graph("histogram")
    # or "log_histogram", "3d", or None
    ...
    if live_graph is not None:
        live_graph.update(gray_frame)   # call once per camera frame
    ...
    if live_graph is not None:
        live_graph.close()

DEPENDENCIES (already required by the rest of this project):
    pip install numpy matplotlib
"""

from __future__ import annotations

import time

import numpy as np
import matplotlib.pyplot as plt


# ==============================================================================
# LIVE HISTOGRAM
# ==============================================================================

class LiveHistogram:
    """
    A bar chart of pixel intensity (0-255) vs. how many pixels have that
    intensity, redrawn every time update() is called.

    Fast by construction:
      * np.bincount() counts every pixel in one vectorized C call instead
        of a Python loop over every pixel (see graph2.py for the slow
        version this replaces).
      * The 256 bar patches are created once in __init__(). Every update
        only changes each bar's height (rect.set_height) instead of
        clearing and rebuilding the whole plot, which is the expensive
        part of a matplotlib redraw.

    Example:
        hist = LiveHistogram()
        hist.update(gray_frame)   # call once per camera frame
        hist.close()
    """

    def __init__(self, window_title: str = "Live Histogram"):
        plt.ion()  # interactive mode: draws never block waiting for a window close
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.fig.canvas.manager.set_window_title(window_title)

        # One bar per possible 8-bit intensity value. Heights start at 0 and
        # are updated in place every frame — the bars themselves are never
        # recreated, which is what keeps this fast enough to run live.
        self._bins = np.arange(256)
        self._bars = self.ax.bar(
            self._bins, np.zeros(256), width=1.0, color="skyblue", edgecolor="none"
        )

        self.ax.set_xlim(0, 255)
        self.ax.set_ylim(0, 1)  # rescaled on the first real update
        self.ax.set_xlabel("Pixel intensity")
        self.ax.set_ylabel("Number of pixels")
        self.ax.set_title(window_title)
        self.fig.tight_layout()

        self._max_count_seen = 1
        plt.show(block=False)

    def is_open(self) -> bool:
        """Return False once the user has closed the window."""
        return plt.fignum_exists(self.fig.number)

    def update(self, frame: np.ndarray) -> None:
        """
        Recompute the histogram for one grayscale frame and redraw.

        Args:
            frame : a 2D uint8 (or any integer/float 0-255) grayscale
                    numpy array, exactly what you already pass to
                    cv2.imshow("Live Feed", frame).
        """
        if not self.is_open():
            return

        counts = np.bincount(frame.astype(np.uint8).ravel(), minlength=256)[:256]

        for rect, count in zip(self._bars, counts):
            rect.set_height(count)

        # Only rescale the y-axis when the tallest bar actually grows, so we
        # are not calling the (comparatively expensive) autoscale machinery
        # on every single frame.
        current_max = counts.max()
        if current_max > self._max_count_seen:
            self._max_count_seen = current_max
            self.ax.set_ylim(0, current_max * 1.1)

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self) -> None:
        if self.is_open():
            plt.close(self.fig)


# ==============================================================================
# LIVE LOG-SCALE HISTOGRAM (LabVIEW-style line plot)
# ==============================================================================

class LiveLogHistogram:
    """
    A dark-themed line plot of pixel intensity (0-255) vs. how many pixels
    have that intensity, on a log-scale y-axis, redrawn every time update()
    is called. Matches the "Number of Pixels vs Pixel Value" style plot
    LabVIEW produces, as a line rather than bars.

    The log scale matters for images with a very bright peak (a large
    number of near-identical background pixels) alongside small numbers of
    much rarer values elsewhere in the range — on a plain linear axis
    (LiveHistogram) that peak would flatten everything else in the plot
    into an invisible sliver near y=0. A log axis keeps the rare values
    visible at the same time as the dominant peak.

    Fast by construction, the same way as LiveHistogram:
      * np.bincount() counts every pixel in one vectorized C call.
      * The line is created once in __init__(). Every update only changes
        its y-data (line.set_ydata) instead of clearing and re-plotting.

    Example:
        hist = LiveLogHistogram()
        hist.update(gray_frame)   # call once per camera frame
        hist.close()
    """

    def __init__(self, window_title: str = "Live Log Histogram"):
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.canvas.manager.set_window_title(window_title)

        self._bins = np.arange(256)
        (self._line,) = self.ax.plot(
            self._bins, np.ones(256), color="white", linewidth=1
        )

        self.ax.set_yscale("log")
        self.ax.set_xlim(0, 255)
        self.ax.set_ylim(1, 10)  # rescaled on the first real update
        self.ax.set_xlabel("Pixel Value")
        self.ax.set_ylabel("Number of Pixels")
        self.ax.set_title(window_title)

        # Dark, LabVIEW-style theme, set once — no need to reapply per frame.
        self.ax.set_facecolor("black")
        self.fig.patch.set_facecolor("black")
        self.ax.tick_params(colors="white")
        self.ax.xaxis.label.set_color("white")
        self.ax.yaxis.label.set_color("white")
        self.ax.title.set_color("white")
        self.fig.tight_layout()

        self._max_count_seen = 1
        plt.show(block=False)

    def is_open(self) -> bool:
        """Return False once the user has closed the window."""
        return plt.fignum_exists(self.fig.number)

    def update(self, frame: np.ndarray) -> None:
        """
        Recompute the histogram for one grayscale frame and redraw.

        Args:
            frame : a 2D uint8 (or any integer/float 0-255) grayscale
                    numpy array, exactly what you already pass to
                    cv2.imshow("Live Feed", frame).
        """
        if not self.is_open():
            return

        counts = np.bincount(frame.astype(np.uint8).ravel(), minlength=256)[:256]
        self._line.set_ydata(counts)

        # A log-scale axis cannot have a limit of 0, so the lower bound
        # stays fixed at 1 — only the upper bound needs to grow to fit.
        current_max = counts.max()
        if current_max > self._max_count_seen:
            self._max_count_seen = current_max
            self.ax.set_ylim(1, max(current_max * 1.5, 10))

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self) -> None:
        if self.is_open():
            plt.close(self.fig)


# ==============================================================================
# LIVE 3D SURFACE PLOT
# ==============================================================================

class LiveSurfacePlot:
    """
    A 3D surface plot of pixel intensity (X = column, Y = row, Z =
    intensity), redrawn a few times per second while the camera runs.

    Two things keep this usable instead of freezing the whole preview:
      * downsample_factor shrinks the grid before plotting (a full
        1920x1200 frame plotted point-for-point would be 2.3 million quads;
        matplotlib's software 3D renderer cannot draw that many quads at
        any usable speed). The default keeps the grid to roughly 130x80.
      * min_interval_s throttles redraws to at most once every
        min_interval_s seconds, regardless of how often update() is
        called. Camera frames can arrive 30+ times a second; a full 3D
        surface cannot realistically redraw that often in matplotlib, so
        extra calls in between are simply skipped rather than queuing up
        and making the whole program fall behind the live feed.

    Example:
        surf = LiveSurfacePlot()
        surf.update(gray_frame)   # call once per camera frame, most calls
                                   # will be skipped by the throttle
        surf.close()
    """

    def __init__(self, window_title: str = "Live 3D Intensity Map",
                 downsample_factor: int = 15, min_interval_s: float = 0.2):
        if downsample_factor < 1:
            raise ValueError(f"downsample_factor must be >= 1, got {downsample_factor}")
        if min_interval_s < 0:
            raise ValueError(f"min_interval_s must be >= 0, got {min_interval_s}")

        plt.ion()
        self.fig = plt.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.fig.canvas.manager.set_window_title(window_title)
        self.ax.set_title(window_title)
        self.ax.set_xlabel("X pixel")
        self.ax.set_ylabel("Y pixel")
        self.ax.set_zlabel("Intensity")
        self.ax.set_zlim(0, 255)

        self.downsample_factor = downsample_factor
        self.min_interval_s = min_interval_s

        self._surface = None
        self._mesh_shape = None   # (height, width) of the last downsampled grid
        self._X = None
        self._Y = None
        self._last_draw_time = 0.0

        plt.show(block=False)

    def is_open(self) -> bool:
        return plt.fignum_exists(self.fig.number)

    def update(self, frame: np.ndarray) -> None:
        """
        Redraw the surface for one grayscale frame, unless less than
        min_interval_s has passed since the last redraw (in which case
        this call is a fast no-op) or the window has been closed.

        Args:
            frame : a 2D uint8 (or any integer/float 0-255) grayscale
                    numpy array, exactly what you already pass to
                    cv2.imshow("Live Feed", frame).
        """
        if not self.is_open():
            return

        now = time.monotonic()
        if now - self._last_draw_time < self.min_interval_s:
            return
        self._last_draw_time = now

        small = frame[::self.downsample_factor, ::self.downsample_factor]
        height, width = small.shape

        # Rebuild the X/Y coordinate grid only when its shape actually
        # changes (first frame, or the camera resolution changed) — this
        # is the same grid every frame otherwise, no need to recompute it.
        if self._mesh_shape != (height, width):
            x = np.arange(width)
            y = np.arange(height)
            self._X, self._Y = np.meshgrid(x, y)
            self._mesh_shape = (height, width)

        # mplot3d has no in-place "update the data" call for a surface —
        # the recommended approach is to remove the old one and add a new
        # one, which is still far cheaper than rebuilding the whole figure.
        if self._surface is not None:
            self._surface.remove()

        self._surface = self.ax.plot_surface(
            self._X, self._Y, small, cmap="viridis", edgecolor="none",
            linewidth=0, antialiased=False,
        )

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self) -> None:
        if self.is_open():
            plt.close(self.fig)


# ==============================================================================
# FACTORY
# ==============================================================================

_GRAPH_TYPES = {
    "histogram": LiveHistogram,
    "log_histogram": LiveLogHistogram,
    "3d": LiveSurfacePlot,
}


def create_live_graph(graph_type: str | None):
    """
    Build the live graph object requested by graph_type, or return None.

    Args:
        graph_type : "histogram", "log_histogram", "3d", or None/"" to
                     disable the live graph entirely (the common case —
                     the graph window costs extra render time, so it is
                     opt-in).

    Returns:
        A LiveHistogram, a LiveLogHistogram, a LiveSurfacePlot, or None.

    Raises:
        ValueError : if graph_type is a non-empty string that isn't one of
                     the recognised types, so a typo fails loudly instead
                     of silently doing nothing.

    Example:
        live_graph = create_live_graph("histogram")
        if live_graph is not None:
            live_graph.update(gray_frame)
    """
    if not graph_type:
        return None

    graph_class = _GRAPH_TYPES.get(graph_type)
    if graph_class is None:
        raise ValueError(
            f"Unknown graph_type: {graph_type!r}. "
            f"Choose from: {', '.join(_GRAPH_TYPES.keys())}, or None."
        )
    return graph_class()


__all__ = [
    "LiveHistogram",
    "LiveLogHistogram",
    "LiveSurfacePlot",
    "create_live_graph",
]
