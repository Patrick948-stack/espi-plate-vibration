"""
test_sidebar_layout.py

Tests for the navigation sidebar layout in monitor_gui.py.

These tests encode seven invariants about sidebar structure, sizing, alignment,
and color. They verify that:
  - The sidebar has a fixed width (I1)
  - The Settings button is positioned at the bottom (I4)
  - All nav elements are properly aligned (I3)
  - Colors are consistent and predictable (I5, I6)
  - Nav list height is fixed, not dynamic (I7)
"""
import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QImage, QColor, QPixmap

# Insert the parent directory of the current file into the system path
sys.path.insert(0, str(Path(__file__).parent.parent))
# Insert a specific subdirectory "ESPI Full Algorithm" within the parent directory into the system path
sys.path.insert(0, str(Path(__file__).parent.parent /"ESPI Full Algorithm"))

# Import the monitor GUI module
import monitor_gui as mg
from monitor_gui import MainWindow

@pytest.fixture
def qapp():
    """
    Create or get the QApplication instance.
    
    PyQt6 requires a single QApplication per test session. pytest-qt handles
    this automatically, but we define it here for clarity.
    If there's no existing QApplication, we create a new one with an empty list of arguments ([]).
    """

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp):
    """
    Create and show a MainWindow instance for testing.

    This fixture:
    1. Instantiates MainWindow
    2. Resizes it to a standard size (900x700, matching the __init__)
    3. Shows it so layout and styling take effect
    4. Yields the window
    5. Cleans up after the test

    The yield keyword pauses the function and provides the MainWindow instance to the test that needs it. pytest will handle pausing and resuming the test as needed.

    pytest-qt's qapp fixture ensures cleanup and signal/slot propagation.
    """
    window = MainWindow()
    window.resize(900, 700)
    window.show()
    yield window
    window.close()


def get_sidebar(main_window):
    """
    Helper function to find the sidebar container.

    The sidebar is the parent of the nav list (main_window._nav).
    We walk up the parent chain from the nav list to find its container.
    """
    nav_list = main_window._nav
    if nav_list is None:
        return None

    # The parent of the nav list is the sidebar container
    sidebar = nav_list.parent()
    return sidebar


def _settle(window):
    """
    Pump the event loop so a resize actually finishes propagating.

    window.update() only schedules a repaint, it does not process the
    event queue, so layout recalculations triggered by resizeEvent() (or,
    since that override was removed, by the nav list's own Expanding size
    policy) never get a chance to run. QApplication.processEvents() is what
    a real windowing system's own event loop would be doing continuously
    while the user drags a window border or clicks the maximize button.
    """
    QApplication.instance().processEvents()

# ============================================================================

# TEST I1: Sidebar width is correct
# ============================================================================
def test_I1_sidebar_has_correct_width(main_window):
    """
    Rule I1: The sidebar container must be exactly 176 pixels wide.

    Why: This creates a consistent layout. If the width changes randomly,
    the UI looks broken, as we have seen it before.

    How this works:
      1. Get the nav list from main_window._nav
      2. Find its parent (the sidebar container)
      3. Check the width
    """
    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Could not find sidebar container"

    expected_width = 176
    actual_width = sidebar.width()

    assert actual_width == expected_width, (
        f"Sidebar width is wrong!\n"
        f"  Expected: {expected_width}px\n"
        f"  Got: {actual_width}px\n"
        f"Fix: Set sidebar width to {expected_width}"
    )

# ============================================================================
# TEST I2: Settings button is inside the sidebar
# ============================================================================

def test_I2_settings_button_is_in_sidebar(main_window):
    """
    Rule I2: The Settings button must be part of the sidebar container.
    
    Why: If the button is not properly connected to the sidebar, it won't
    move or style correctly with the rest of the sidebar.
    
    How this works:
      1. Get the Settings button (we know it exists: main_window.settings_button)
      2. Walk up the parent chain (button → parent → parent → ...)
      3. Check if we eventually reach a sidebar container
      4. If we do, the test passes. If not, something is wrong with how
         the button was added to the layout.
    """
    # Get the Settings button
    settings_button = main_window.settings_button
    assert settings_button is not None, "Settings button not found on window"
    
    # Walk up the parent chain (up to 10 levels) looking for the sidebar
    current_widget = settings_button
    found_sidebar = False
    
    for step in range(10):
        # Get the parent of the current widget
        parent = current_widget.parent()
        
        # Stop if we've reached the top (no more parents)
        if parent is None:
            break
        
        # Check if this parent is the sidebar
        # (The sidebar is the one that contains the NavRail list)
        if hasattr(parent, 'layout') and parent.layout() is not None:
            for i in range(parent.layout().count()):
                child = parent.layout().itemAt(i).widget()
                if child is not None:
                    if hasattr(child, 'objectName'):
                        if child.objectName() == 'NavRail':
                            found_sidebar = True
                            break
        
        if found_sidebar:
            break
        
        # Move up one level
        current_widget = parent
    
    # Check result
    assert found_sidebar, (
        "Settings button is not connected to the sidebar!\n"
        "Fix: Make sure settings_button is added to nav_layout"
    )

# ============================================================================
# TEST I3: Settings button spans the full sidebar width
# ============================================================================

def test_I3_settings_button_spans_full_width(main_window):
    """
    Rule I3: The Settings button should be as wide as the sidebar.

    Why: It looks wrong if the button is narrower than the sidebar or
    shifted to one side.

    How this works:
      1. Find the sidebar container
      2. Find the Settings button
      3. Check that the button's left and right edges match the sidebar's edges
         (accounting for layout margins of 8px on each side)
      4. If they don't match, the button is misaligned
    """
    # Get the Settings button
    settings_button = main_window.settings_button
    assert settings_button is not None, "Settings button not found"

    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"
    
    # Get the positions and sizes 
    # __`geometry()`__ is a Qt method that returns a rectangle with 
    # the widget's __position and size__ — specifically `(x, y, width, height)`.


    button_rect = settings_button.geometry()
    # __`rect()`__ is similar to `geometry()`, but it returns the rectangle 
    # __relative to the widget itself__ (not the screen). So the top-left corner is always (0, 0).

    sidebar_rect = sidebar.rect()
    
    # The sidebar has 8px margin on each side, so the button can be 8px from the edge
    margin = 8
    
    # Check left alignment
    # - __`left()`__ → the x-coordinate of the left edge
    # - __`right()`__ → the x-coordinate of the right edge (= left + width - 1)

    ## Left edge check: button should start at least 6px from the left
    assert button_rect.left() >= margin - 2, (
        f"Settings button left edge is at {button_rect.left()}px, "
        f"but sidebar left margin is {margin}px. Button is too far left."
    )
    
    # Check right alignment
    # Right edge check: button should end at most 2px past the margin
    expected_right = sidebar_rect.width() - margin
    assert button_rect.right() <= expected_right + 2, (
        f"Settings button right edge is at {button_rect.right()}px, "
        f"but sidebar right edge is at {expected_right}px. Button is too far right."
    )

# ============================================================================
# TEST I4: Sidebar fills the full window height
# ============================================================================

def test_I4_sidebar_is_full_height(main_window):
    """
    Rule I4: The sidebar should be as tall as the window's content area.

    Why: If the sidebar is shorter than the window, you'll see the window
    background showing through at the bottom, which looks wrong.

    How this works:
      1. Find the sidebar container
      2. Find the central widget (the area containing sidebar + main content)
      3. Compare their heights
      4. They should be the same (within a few pixels for rounding)
    """
    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"
    
    # Get the central widget (the container for sidebar + content)
    central = main_window.centralWidget()
    assert central is not None, "Central widget not found"
    
    # Get the heights
    sidebar_height = sidebar.height()
    central_height = central.height()
    
    # They should be very close (within 5 pixels for rounding/spacing)
    height_difference = abs(sidebar_height - central_height)
    
    assert height_difference < 5, (
        f"Sidebar height doesn't match window height!\n"
        f"  Sidebar height: {sidebar_height}px\n"
        f"  Window height: {central_height}px\n"
        f"  Difference: {height_difference}px\n"
        f"Fix: Set sidebar size policy to Expanding vertically"
    )


# ============================================================================
# TEST I5: Sidebar background is the correct color
# ============================================================================

def test_I5_sidebar_background_color(main_window):
    """
    Rule I5: The sidebar background should be a dark gray (#171717).

    Why: If the color is wrong, it was probably not painted from the
    stylesheet, which means QSS styling isn't working.

    How this works:
      1. Render the sidebar as an image (pixel-by-pixel screenshot)
      2. Sample pixels from different spots down the left edge
      3. Check if they're all the dark gray color we expect
      4. If they're a different color, the background isn't being painted

    Note on QImage: QImage is like a screenshot. We render the sidebar
    into a QImage, then check individual pixels to see what color they are.
    """
    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"
    
    # Force the widget to update its layout before we render it
    sidebar.update()
    
    # Render the sidebar as an image
    # This is like taking a screenshot of just the sidebar
    image = QImage(sidebar.size(), QImage.Format.Format_RGB32)
    sidebar.render(image)
    
    # The expected color is #171717 (dark gray)
    # In RGB, that's: R=0x17 (23), G=0x17 (23), B=0x17 (23)
    expected_color = QColor(0x17, 0x17, 0x17)
    
    # Sample pixels at the left edge (x=0) every 50 pixels down
    # We don't check every single pixel because rendering can be slightly imperfect
    gutter_x = 0
    tolerance = 20  # Allow ±20 on each color channel for rendering artifacts
    
    for y in range(0, image.height(), 50):
        # Get the color of the pixel at this location
        pixel_color = QColor(image.pixelColor(gutter_x, y))
        
        # Compare it to the expected color
        r_diff = abs(pixel_color.red() - expected_color.red())
        g_diff = abs(pixel_color.green() - expected_color.green())
        b_diff = abs(pixel_color.blue() - expected_color.blue())
        
        # If any channel is too far off, the color is wrong
        assert r_diff < tolerance and g_diff < tolerance and b_diff < tolerance, (
            f"Sidebar background color is wrong at pixel (0, {y})!\n"
            f"  Expected: {expected_color.name()} (RGB {expected_color.red()}, "
            f"{expected_color.green()}, {expected_color.blue()})\n"
            f"  Got: {pixel_color.name()} (RGB {pixel_color.red()}, "
            f"{pixel_color.green()}, {pixel_color.blue()})\n"
            f"Fix: Sidebar needs background-color in QSS and "
            f"WA_StyledBackground attribute"
        )


# ============================================================================
# TEST I6: Settings button background matches sidebar at rest
# ============================================================================

def test_I6_settings_button_background_color(main_window):
    """
    Rule I6: When not hovered, the Settings button should look like part of
    the sidebar (same background color).

    Why: The button blends into the sidebar at rest. When you hover over it,
    it gets a different color to show it's clickable. This gives visual
    feedback without making it stand out all the time.

    How this works:
      1. Render the sidebar as an image (like a screenshot)
      2. Find where the Settings button is on that image
      3. Look at the pixel in the center of the button
      4. Check if it's the same dark gray as the sidebar background
      5. If it's a different color, the button's background is not transparent
    """
    # Get the Settings button
    settings_button = main_window.settings_button
    assert settings_button is not None, "Settings button not found"

    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"
    
    # Render the sidebar as an image
    sidebar.update()
    image = QImage(sidebar.size(), QImage.Format.Format_RGB32)
    sidebar.render(image)
    
    # Get the button's position and size
    button_rect = settings_button.geometry()
    
    # Find the center of the button
    button_center_x = button_rect.center().x()
    button_center_y = button_rect.center().y()
    
    # The expected color is the sidebar background (#171717)
    expected_color = QColor(0x17, 0x17, 0x17)
    
    # Get the actual color at the button's center
    pixel_color = QColor(image.pixelColor(int(button_center_x), int(button_center_y)))
    
    # Check if they match (with some tolerance for rendering)
    tolerance = 30  # Allow ±30 on each color channel
    r_diff = abs(pixel_color.red() - expected_color.red())
    g_diff = abs(pixel_color.green() - expected_color.green())
    b_diff = abs(pixel_color.blue() - expected_color.blue())
    
    assert r_diff < tolerance and g_diff < tolerance and b_diff < tolerance, (
        f"Settings button doesn't match the sidebar background!\n"
        f"  Expected: {expected_color.name()} (RGB {expected_color.red()}, "
        f"{expected_color.green()}, {expected_color.blue()})\n"
        f"  Got: {pixel_color.name()} (RGB {pixel_color.red()}, "
        f"{pixel_color.green()}, {pixel_color.blue()})\n"
        f"Fix: Button background should be 'transparent' in QSS"
    )


# ============================================================================
# TEST I7: Nav list expands with window, sidebar width stays fixed
# ============================================================================

def test_I7_nav_list_expands_with_window(main_window):
    """
    Rule I7: The nav list should grow as tall as the window, but the sidebar
    should stay at a fixed width.

    Why: When the user makes the window taller, the sidebar should stay the
    same width, but the nav list should expand to fill the extra vertical
    space. The Settings button stays at the bottom.

    How this works:
      1. Get the sidebar and nav list sizes at the starting window size (900x700)
      2. Make the window much taller (900x1000)
      3. Check that:
         - Sidebar width is still 176px (didn't change)
         - Nav list is now taller than before (grew with the window)
         - Settings button is still at the bottom
    """
    # Find the sidebar container
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"
    
    # Get the nav list widget
    nav_list = main_window._nav
    assert nav_list is not None, "Nav list not found"
    
    # Get the Settings button
    settings_button = main_window.settings_button
    assert settings_button is not None, "Settings button not found"
    
    # --------
    # BEFORE: Record the initial sizes
    # --------
    initial_sidebar_width = sidebar.width()
    initial_nav_height = nav_list.height()
    initial_window_height = main_window.height()
    
    # The sidebar width should be 176px
    assert initial_sidebar_width == 176, (
        f"Sidebar should start at width 176px, but is {initial_sidebar_width}px"
    )
    
    # --------
    # RESIZE: Make the window much taller
    # --------
    # NOTE: show() already grows the window to fit its content's natural
    # minimum height (around 970px, driven by the Setup page's group boxes,
    # not the sidebar), regardless of what resize(900, 700) asked for. So
    # initial_window_height above is NOT 700, and the target here has to be
    # comfortably larger than that natural minimum for this test to prove
    # anything about growth, rather than just re-measuring the same floor.
    new_window_height = 1400
    main_window.resize(900, new_window_height)
    _settle(main_window)  # let the resize actually propagate through the layout

    # --------
    # AFTER: Check the new sizes
    # --------
    final_sidebar_width = sidebar.width()
    final_nav_height = nav_list.height()
    final_window_height = main_window.height()

    # Rule 1: Sidebar width should NOT change
    # It stays at 176px regardless of window height
    assert final_sidebar_width == initial_sidebar_width, (
        f"Sidebar width changed!\n"
        f"  Before: {initial_sidebar_width}px\n"
        f"  After: {final_sidebar_width}px\n"
        f"Fix: Sidebar should have fixed width of 176px"
    )

    # Rule 2: Nav list should grow taller
    # When the window gets taller, the nav list should expand to use that space.
    # It shares the leftover space with nav_layout's addStretch() roughly
    # 50/50, so it won't absorb 100% of the window's growth, just a
    # meaningful share of it.
    height_increase = final_nav_height - initial_nav_height
    window_height_increase = final_window_height - initial_window_height

    assert height_increase > 100, (
        f"Nav list didn't grow when window was resized!\n"
        f"  Window height increase: {window_height_increase}px\n"
        f"  Nav list height increase: {height_increase}px\n"
        f"Fix: Nav list should have Expanding vertical size policy"
    )
    
    # Rule 3: Settings button should still be at the bottom
    # Get the position of the Settings button relative to the sidebar
    button_bottom = settings_button.geometry().bottom()
    sidebar_bottom = sidebar.geometry().height()
    distance_from_bottom = sidebar_bottom - button_bottom
    
    assert distance_from_bottom < 5, (
        f"Settings button is not at the bottom of the sidebar!\n"
        f"  Distance from bottom: {distance_from_bottom}px\n"
        f"Fix: Check that the stretch() is placed correctly in nav_layout"
    )


# ============================================================================
# TEST I8: Sidebar never grows taller than the window itself
# ============================================================================

def test_I8_sidebar_height_never_exceeds_window_height(main_window):
    """
    Rule I8: No matter how large the window gets, the sidebar (and the nav
    list inside it) must never be taller than the window's own content area.

    Why: resizeEvent() used to force the nav list's min/max height from a
    value computed off the sidebar's OWN current height, which is stale at
    the moment resizeEvent() fires since Qt has not relaid out the child
    yet for the new window size. Combined with a conflicting QSS max-height
    on the nav list, each resize pushed the sidebar's computed height
    further past the window's actual height instead of settling on one. At
    full screen sizes this grew large enough that sidebar content got
    pushed off screen or overlapped into invisibility, the "window
    squeezes until it disappears" bug.
    """
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"

    for width, height in [(1920, 1080), (2560, 1440), (1440, 900), (1728, 1117)]:
        main_window.resize(width, height)
        _settle(main_window)

        assert sidebar.height() <= main_window.height(), (
            f"Sidebar is taller than the window at {width}x{height}!\n"
            f"  Window height: {main_window.height()}px\n"
            f"  Sidebar height: {sidebar.height()}px\n"
            f"Fix: Don't force nav list height from a resizeEvent override; "
            f"let the Expanding size policy manage it instead."
        )


def test_I8b_sidebar_widgets_stay_visible_with_positive_height_at_full_screen(main_window):
    """
    Rule I8b: At a full screen sized window, every sidebar widget (nav list,
    Settings button) must keep a positive height and stay visible, never
    shrink to zero or a negative height.
    """
    nav_list = main_window._nav
    settings_button = main_window.settings_button

    main_window.resize(1920, 1080)
    _settle(main_window)

    assert nav_list.height() > 0, "Nav list height collapsed to zero or negative"
    assert nav_list.isVisible(), "Nav list is no longer visible at full screen size"
    assert settings_button.height() > 0, "Settings button height collapsed"
    assert settings_button.isVisible(), "Settings button is no longer visible at full screen size"


# ============================================================================
# TEST I9: Repeated resizes to the same size do not cause runaway growth
# ============================================================================

def test_I9_repeated_resize_to_same_size_is_stable(main_window):
    """
    Rule I9: Resizing to the same size more than once in a row must produce
    the same sidebar height each time, not a progressively larger one.

    Why: the previous resizeEvent() implementation read the sidebar's
    current (already grown from last time) height to compute the nav
    list's next forced height, so each additional resize, even to the same
    target size, grew the sidebar further instead of settling. A stable
    layout should be idempotent: resizing to the same size twice should
    look the same both times.
    """
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"

    main_window.resize(1920, 1080)
    _settle(main_window)
    first_height = sidebar.height()

    main_window.resize(1920, 1080)
    _settle(main_window)
    second_height = sidebar.height()

    assert second_height == first_height, (
        f"Sidebar height changed on a repeated resize to the same size!\n"
        f"  First resize: {first_height}px\n"
        f"  Second resize: {second_height}px\n"
        f"Fix: resizeEvent() must not compute the nav list's new height from "
        f"the sidebar's own already-updated height."
    )


def test_I9b_shrinking_back_down_after_full_screen_still_works(main_window):
    """
    Rule I9b: Growing the window to full screen size and then shrinking it
    back down to a normal size must not leave the sidebar permanently
    corrupted or oversized from the earlier large resize.
    """
    sidebar = get_sidebar(main_window)
    assert sidebar is not None, "Sidebar not found"

    main_window.resize(2560, 1440)
    _settle(main_window)

    main_window.resize(900, 700)
    _settle(main_window)

    assert sidebar.width() == 176
    assert sidebar.height() <= main_window.height()


def test_I9c_window_can_actually_shrink_back_to_its_original_size(main_window):
    """
    Rule I9c: This is the exact bug the student hit maximizing the window.

    resizeEvent() used to call self._nav.setMinimumHeight(available_height)
    every time it fired, where available_height was computed from the
    sidebar's OWN current height. Setting a widget's minimum height doesn't
    just describe its size, it raises the floor Qt will ever allow that
    widget (and therefore the window containing it) to shrink to. Because
    each resize computed a bigger minimum from an already-inflated height,
    growing the window once to full screen permanently raised the window's
    minimum size, so asking to shrink back to the original 900x700 size
    afterward silently got clamped to something much taller instead. On a
    real desktop, the maximize/fullscreen transition fires several resize
    events in a row while animating, each one raising the floor further
    before the window finishes growing, which is what the visible
    "squeezing until it disappears" symptom actually was.
    """
    main_window.resize(2560, 1440)
    _settle(main_window)

    main_window.resize(900, 700)
    _settle(main_window)

    # Compare against a completely fresh window that goes straight to
    # 900x700 with no detour through a huge size first. Comparing against
    # main_window's own pre-test height isn't decisive on its own: show()
    # can already establish an inflated floor before this test's resizes
    # even run, so a same-window before/after comparison can pass even
    # when the underlying ratchet is real. A fresh, uncontaminated window
    # is the only reliable baseline.
    from monitor_gui import MainWindow as _MainWindow
    fresh_window = _MainWindow()
    fresh_window.resize(900, 700)
    fresh_window.show()
    _settle(fresh_window)

    assert main_window.height() == fresh_window.height(), (
        f"Window could not shrink back to a normal size after growing large!\n"
        f"  Fresh window at 900x700: {fresh_window.height()}px\n"
        f"  main_window after growing huge then resize(900, 700): {main_window.height()}px\n"
        f"Fix: Don't call setMinimumHeight()/setMaximumHeight() with a value "
        f"derived from the sidebar's own current (possibly already inflated) "
        f"height inside resizeEvent()."
    )
    fresh_window.close()


# ============================================================================
# TEST I10: SettingsPage does not force the whole window to grow past the screen
# ============================================================================

def test_I10_settings_page_minimum_height_stays_small(main_window):
    """
    Rule I10: SettingsPage's minimumSizeHint() must stay small (bounded),
    the same way SetupPage's already does.

    Why: QStackedWidget must be big enough to show ANY of its pages, even
    ones not currently visible, so its own minimum size is the max across
    every page's minimum size. SetupPage is already wrapped in a
    QScrollArea for exactly this reason (see its own docstring), but
    SettingsPage was not: as Learn More buttons and CLAHE/gamma controls
    were added to it, its minimumSizeHint() grew to 948px tall, well past
    many real screens, which forced the whole window (and therefore the
    Setup page the user actually launches into) to be at least that tall
    too. That's what cropped the Settings button and the Live Monitor
    control row off the bottom of the screen.
    """
    settings_hint = main_window.settings_page.minimumSizeHint()

    assert settings_hint.height() < 300, (
        f"SettingsPage's minimum height is {settings_hint.height()}px, which is "
        f"what forces the whole window to be at least that tall.\n"
        f"Fix: Wrap SettingsPage's content in a QScrollArea, the same way "
        f"SetupPage already does."
    )


def test_I10b_stack_minimum_height_no_longer_dominated_by_settings(main_window):
    """
    Rule I10b: The QStackedWidget's minimum height should track whichever
    page actually needs the most room to be usable (LiveMonitorPage, with
    its two feed labels), not SettingsPage, once SettingsPage scrolls.
    """
    stack_hint = main_window._stack.minimumSizeHint()
    live_monitor_hint = main_window.live_monitor_page.minimumSizeHint()

    assert stack_hint.height() <= live_monitor_hint.height() + 50, (
        f"Stack minimum height ({stack_hint.height()}px) is still much taller "
        f"than LiveMonitorPage's own minimum height "
        f"({live_monitor_hint.height()}px), so something is still forcing "
        f"the window to be taller than necessary."
    )


# ============================================================================
# TEST I11: The window fits on screen at launch, regardless of screen size
# ============================================================================

def test_I11_window_fits_within_available_screen_at_launch(qapp):
    """
    Rule I11: A freshly launched MainWindow must fit within the primary
    screen's available geometry, so nothing (the Settings button, the Live
    Monitor page's control row) ends up rendered off screen.

    Why: the student's real screen showed the Settings button and the Live
    Monitor button row cropped off the bottom. This project's test screen
    (the offscreen QPA platform's virtual display) is 800x800, and a fresh
    MainWindow used to come up at 970px tall even before touching
    anything, already taller than an 800px-tall screen. That is the exact
    bug, reproduced directly instead of guessed at.
    """
    window = MainWindow()
    window.show()
    QApplication.instance().processEvents()

    screen = QApplication.instance().primaryScreen()
    available = screen.availableGeometry()

    assert window.height() <= available.height(), (
        f"Window is {window.height()}px tall, but the available screen is "
        f"only {available.height()}px tall!\n"
        f"Fix: clamp the window's initial size to the screen's available "
        f"geometry, and make sure no page's content forces the window "
        f"taller than that (see I10)."
    )

    # Width is not held to the same strict bound as height. LiveMonitorPage
    # shows two video feeds side by side, each with its own setMinimumSize()
    # so a live camera frame is actually visible rather than a postage
    # stamp; that is a legitimate minimum, not a bug, and it can genuinely
    # exceed an unusually narrow or square screen (the offscreen test
    # platform's own virtual screen is an 800x800 square, narrower than
    # this window's content needs). Only guard against a gross, accidental
    # overflow far beyond what the feed labels themselves require.
    assert window.width() <= available.width() + 100, (
        f"Window is {window.width()}px wide, far past the available screen "
        f"width of {available.width()}px, more than the live feed labels' "
        f"own minimum size can account for."
    )
    window.close()


# ============================================================================
# TEST I12: Nav and Settings icons render in the bright primary text color
# ============================================================================

def _dominant_icon_color(icon, size=24):
    """
    Render a QIcon to a pixmap and return the most common non-transparent
    pixel color. A single center-pixel sample is not reliable for glyph
    icons: a gear or tune icon's exact center point often falls on empty
    space between strokes, which would silently pass a broken test. Scanning
    every pixel and picking the most common painted color reflects what the
    icon actually looks like.
    """
    pixmap = icon.pixmap(QSize(size, size))
    image = pixmap.toImage()
    counts = {}
    for x in range(size):
        for y in range(size):
            color = image.pixelColor(x, y)
            if color.alpha() > 100:
                counts[color.getRgb()] = counts.get(color.getRgb(), 0) + 1
    assert counts, "Icon rendered nothing (fully transparent), can't sample a color"
    most_common_rgba = max(counts, key=counts.get)
    return QColor(*most_common_rgba)


def _assert_bright_not_grey(name, color):
    expected = QColor("#e0e0e0")
    tolerance = 40
    diff = (
        abs(color.red() - expected.red())
        + abs(color.green() - expected.green())
        + abs(color.blue() - expected.blue())
    )
    assert diff < tolerance, (
        f"{name} icon color is {color.name()}, expected close to "
        f"{expected.name()} (bright, not grey or black).\n"
        f"Fix: pass color=QColor(_TEXT_PRIMARY) when building this icon "
        f"with qta.icon()."
    )


def test_I12_setup_and_live_monitor_icons_are_bright_not_grey(main_window):
    """
    Rule I12: The Setup and Live Monitor nav icons must render in the
    bright primary text color (#e0e0e0), not the muted grey secondary
    color, so they read clearly against the dark sidebar regardless of
    whether their row is currently selected.
    """
    setup_icon = main_window._nav.item(0).icon()
    monitor_icon = main_window._nav.item(1).icon()

    _assert_bright_not_grey("Setup", _dominant_icon_color(setup_icon))
    _assert_bright_not_grey("Live Monitor", _dominant_icon_color(monitor_icon))


def test_I12b_settings_icon_is_bright_not_grey(main_window):
    """Rule I12b: same as I12, for the Settings button's icon."""
    settings_icon = main_window.settings_button.icon()
    _assert_bright_not_grey("Settings", _dominant_icon_color(settings_icon))


# ============================================================================
# TEST I13: Selected nav row keeps its highlight even when the window is inactive
# ============================================================================

def test_I13_selected_row_style_covers_inactive_window_state(main_window):
    """
    Rule I13: Qt style sheets only apply `::item:selected` to a fully
    focused ("active") widget by default on some platforms; when the
    window is not the active/focused one (e.g. right after clicking a
    button that doesn't give the nav list focus, which is the normal case
    here), an item view can silently fall back to a much fainter native
    highlight unless the stylesheet explicitly also covers the
    :selected:!active state. This is exactly why the student saw Setup
    highlight correctly but Live Monitor never visibly change color after
    clicking into it on a real desktop, even though the item WAS correctly
    selected according to Qt's own selection model the whole time.
    """
    stylesheet = mg._STYLESHEET if hasattr(mg, "_STYLESHEET") else None
    assert stylesheet is not None, "Could not find _STYLESHEET to inspect"
    assert "NavRail::item:selected" in stylesheet
    assert ":!active" in stylesheet, (
        "QListWidget#NavRail's selected-item style has no :!active rule, "
        "so the highlight can disappear whenever the window (or just the "
        "nav list) isn't the focused widget, which is the normal case when "
        "the user clicks Start Monitor and the button, not the nav list, "
        "has focus.\n"
        "Fix: add a QListWidget#NavRail::item:selected:!active rule with "
        "the same background-color/color/border-left as the plain "
        "::item:selected rule."
    )
