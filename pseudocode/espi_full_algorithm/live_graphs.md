# ESPI Full Algorithm/live_graphs.py - Real-Time Graph Generation

## Purpose

This file provides live, updating graphs that show pixel intensity data from the camera in real-time. As frames come in, the graphs update to show what the camera is capturing. This helps users understand the data and verify camera settings are correct.

## Graph Types

The module offers three different graph styles:

1. **LiveHistogram** - Bar chart of pixel intensity distribution
2. **LiveLogHistogram** - Bar chart with logarithmic scale (good for data with large ranges)
3. **LiveSurfacePlot** - 3D surface showing intensity across the image

Each can run in its own window or be embedded in a PyQt6 GUI.

## Key Concept: "Live" Means Efficient Updates

A naive approach would recreate the entire graph from scratch every frame. This is slow. Instead:

1. Create the graph once with empty data
2. Every frame, update only the data values in place
3. Redraw only what changed

This keeps frame rates smooth even on large images.

## How Graphs Are Created

To use these graphs, you call a factory function:

```python
live_graph = live_graphs.create_live_graph("histogram")
```

This returns a graph object with these methods:
- `update(frame)` - Feed a new frame to the graph
- `close()` - Shut down the graph window
- `is_open()` - Check if the user closed the window

## LiveHistogram Class

### Purpose

Shows a bar chart with pixel intensity (0-255) on the x-axis and count of pixels on the y-axis.

### __init__(window_title, ax=None)

**What it does:**
1. Determine if we own the figure (ax is None) or embedding in an existing axes
2. If standalone, create a matplotlib figure and axes
3. Turn on interactive mode (drawing doesn't block)
4. Create 256 bar objects (one per possible intensity value 0-255)
5. Set up axes labels and limits
6. Show the figure (if standalone)

**Parameters:**
- `window_title`: Title for the window
- `ax`: Optional existing matplotlib axes to draw into (for embedding in GUI)

### update(frame)

**What it does:**
1. Check if the graph window is still open
2. Convert the frame to uint8 format
3. Flatten the frame to a 1D array of all pixels
4. Use numpy.bincount() to count pixels at each intensity level
5. For each of the 256 bars, update its height to the count
6. Rescale y-axis if needed (only when a taller bar appears)
7. Redraw the graph

**Why numpy.bincount() is fast:**
- Written in C and optimized
- Counts all pixels in one vectorized operation
- Instead of looping through every pixel with Python (slow), does it all in compiled code (fast)

### is_open()

**What it does:**
1. If embedded in GUI (not owning figure), always return True
2. If standalone, check if matplotlib figure still exists
3. Return True if window is open, False if user closed it

**Why this matters:** Allows code to stop updating the graph once the user closes it.

## LiveLogHistogram Class

### Purpose

Like LiveHistogram, but the y-axis uses logarithmic scale instead of linear. This is useful when data has a huge range (like a background peak with many pixels vs. few pixels at other intensities).

### How It Works

Same as LiveHistogram but with:
1. y-axis set to log scale
2. Useful for LabVIEW-style plots
3. Dark theme to match ESPI lab aesthetics

## LiveSurfacePlot Class

### Purpose

Shows a 3D surface plot where:
- X-axis is horizontal position in image
- Y-axis is vertical position in image
- Z-axis is pixel intensity at that position

This lets you see the spatial pattern of brightness across the image.

### Performance Note

matplotlib's 3D renderer is pure Python and slow. It:
1. Depth-sorts every polygon every redraw
2. No GPU acceleration
3. Cannot redraw at full frame rate (15-30+ fps)

**Solution:** Throttle updates to a few times per second instead of every frame. The result is still "live" just at a lower refresh rate.

### __init__(window_title, ax=None, fps=2)

**What it does:**
1. Set up matplotlib figure with 3D axes (if standalone)
2. Create 3D surface plot with sample data
3. Set update throttle (default 2 fps)
4. Initialize last update timestamp

### update(frame)

**What it does:**
1. Check if enough time has passed (throttle check)
2. If not enough time: return without updating
3. If time has passed:
   - Update surface Z data with new frame
   - Rescale Z-axis if needed
   - Redraw the plot
   - Record current timestamp

This throttling keeps the 3D view responsive without crushing performance.

## Factory Function: create_live_graph()

### Purpose

Central place to create the right graph type.

### How It Works

```python
live_graph = create_live_graph("histogram")
live_graph = create_live_graph("log_histogram")
live_graph = create_live_graph("3d")
live_graph = create_live_graph(None)  # No graph
```

**What it does:**
1. Check the graph_type parameter
2. Return appropriate graph class instance
3. Return None if graph_type is None or unrecognized

### Why Useful

Allows code to enable/disable graphs via a settings parameter without checking what type is requested everywhere.

## Embedding in PyQt6 GUI

All graph classes accept an `ax` parameter. If provided:
1. The graph draws into that matplotlib axes
2. The axes is embedded in a PyQt6 window (using FigureCanvasQTAgg)
3. The GUI owns the figure, not the graph class
4. Closing the GUI window closes the graph

**Example from monitor_gui.py:**
```python
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt
import live_graphs

fig, ax = plt.subplots()
graph = live_graphs.LiveHistogram(ax=ax)
canvas = FigureCanvasQTAgg(fig)
layout.addWidget(canvas)

# In the main loop:
frame = capture_from_camera()
graph.update(frame)
```

## Typical Usage in Monitoring Mode

1. User selects which graph to display (histogram, log histogram, 3D, or none)
2. Create the graph: `graph = create_live_graph(user_choice)`
3. In the capture loop:
   ```
   while running:
       frame = grab_frame()
       display_frame(frame)
       if graph is not None and graph.is_open():
           graph.update(frame)
   ```
4. When done: `if graph: graph.close()`

## Performance Considerations

### LiveHistogram
- Uses numpy.bincount (C-optimized)
- Updates 256 bar heights (not recreating entire plot)
- Can handle 30+ fps on typical images

### LiveLogHistogram
- Same as LiveHistogram but with log scale
- Slightly slower due to log math but still live

### LiveSurfacePlot
- Throttled to 2-3 fps
- Much heavier computation (3D depth sorting)
- Still responsive for user feedback

## Related Files

- monitor.py - Uses graphs in monitoring mode
- monitor_gui.py - Embeds graphs in PyQt6 window
- capture_and_display.py - Shows graphs during capture
- run_experiment.py - Analyzes intensity during frequency sweep
