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
from PyQt6.QtCore import QSize, QRect
from PyQt6.QtGui import QImage, QColor

# Insert the parent directory of the current file into the system path
sys.path.insert(0, str(Path(__file__).parent.parent))
# Insert a specific subdirectory "ESPI Full Algorithm" within the parent directory into the system path
sys.path.insert(0, str(Path(__file__).parent.parent /"ESPI Full Algorithm"))

# Import the monitor GUI module
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
    new_window_height = 1000  # Taller than the initial 700px
    main_window.resize(900, new_window_height)
    main_window.update()  # Force the layout to recalculate
    
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
    # When the window gets taller, the nav list should expand to use that space
    height_increase = final_nav_height - initial_nav_height
    window_height_increase = new_window_height - initial_window_height
    
    assert height_increase > 50, (
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
