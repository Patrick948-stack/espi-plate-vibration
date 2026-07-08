# live_graphs.py — Plain-Language Pseudocode

## What this file is for

An optional third preview window for `monitor.py` and the
`capture_and_display*.py` scripts: a live graph of the raw camera frame's
pixel intensity, either a histogram or a 3D surface. It replaces two
exploratory scripts, `Learning/graph.py` (3D surface of one saved image
file) and `Learning/graph2.py` (histogram of one saved image file) —
neither of those worked for a live feed, since both read a file from disk
and both called the blocking `plt.show()`, which freezes a program until
the window is closed by hand.

## Why a live version needs different code, not just a loop around the old one

```
Learning/graph.py and graph2.py, called every frame, would:
    read a file from disk               # a live frame never touches disk
    open a brand new blocking window    # plt.show() halts everything until
                                         # that window is closed — the very
                                         # first frame would freeze the program
    (graph2.py specifically) count pixels with a Python "for pixel in image"
        loop — for a 1920x1200 frame that is 2.3 million Python-level loop
        iterations, far too slow to repeat every frame
```

Both problems are solved the same way: build the matplotlib figure ONCE,
then update its data in place every frame instead of rebuilding it.

## LiveHistogram

```
class LiveHistogram:
    function __init__():
        turn on matplotlib's interactive mode (draws never block)
        create one figure with one bar per intensity value 0-255,
            all starting at height 0
        # the bars are created exactly once here — updating an existing
        # bar's height is cheap, recreating 256 bars from scratch is not

    function is_open():
        return whether the user has closed this window

    function update(frame):
        if the window was closed: do nothing
        counts = np.bincount(frame, one bucket per value 0-255)
            # a single vectorized C-level call, not a Python loop —
            # this is the fix for graph2.py's slow pixel-counting loop
        for each bar, set its height to the matching count
        only rescale the y-axis if the tallest bar grew past the current
            axis limit (skips the more expensive autoscale most frames)
        redraw just the changed parts of the figure

    function close():
        close the window if still open
```

## LiveSurfacePlot

```
class LiveSurfacePlot:
    function __init__(downsample_factor=15, min_interval_s=0.2):
        turn on matplotlib's interactive mode
        create one empty 3D figure (X = column, Y = row, Z = intensity)
        remember downsample_factor and min_interval_s, remember "never
            drawn yet" as the last-draw time

    function is_open():
        return whether the user has closed this window

    function update(frame):
        if the window was closed: do nothing
        if less time than min_interval_s has passed since the last redraw:
            do nothing  # this is the throttle — see "why" below
        downsample frame by keeping every Nth row and column
            (N = downsample_factor)
        rebuild the X/Y coordinate grid only if the downsampled shape
            changed since last time (normally it never does)
        remove the previous surface, if any, and draw a new one from the
            downsampled data
            # mplot3d has no "just update the data" call for a surface —
            # remove-and-redraw is the standard, still much cheaper than
            # rebuilding the whole figure from scratch
        redraw just the changed parts of the figure

    function close():
        close the window if still open
```

### Why the 3D plot is throttled and the histogram isn't

matplotlib's 3D renderer (`mplot3d`) is pure Python and not GPU
accelerated — it depth-sorts every quad in the surface by hand on every
single redraw. A camera can deliver 15-30+ frames a second; there is no
downsample factor that makes a full 3D surface redraw keep up with that in
matplotlib. `min_interval_s` caps redraws to a few times a second instead —
still clearly live, just not frame-locked to the camera. The histogram has
no such ceiling: it only ever redraws 256 numbers, so it can genuinely
track every single frame.

## create_live_graph(graph_type)

```
function create_live_graph(graph_type):
    if graph_type is None or empty string: return None
        # this is the default — most of the time nobody wants the extra
        # window, so it costs nothing unless explicitly requested
    if graph_type is "histogram": return a new LiveHistogram()
    if graph_type is "3d": return a new LiveSurfacePlot()
    otherwise: raise an error naming the valid choices
        # a typo like "histogramm" fails loudly here instead of the graph
        # window just silently never appearing
```

## How the capture_and_display*.py scripts use this

```
live_graph = create_live_graph(graph_type)   # None unless requested

... inside the grab loop, right after showing "Live Feed" ...
if live_graph is not None:
    live_graph.update(frame)   # the RAW frame, not the subtraction diff

... when the loop ends ...
if live_graph is not None:
    live_graph.close()
```

The graph always tracks the raw "Live Feed" frame, not the "Frame
Subtraction" difference image — the intensity of the actual incoming image
is what the histogram/3D view are for.

## Why this file exists

`monitor.py`'s "current focus" note in the project's own instructions was
literally "find the best graph to represent pixel number vs intensity for
any given image" and "embed the graph function in capture and display for
the live feed frames." `Learning/graph.py` and `graph2.py` were the
exploration that answered the first half of that (a 3D surface and a
histogram are both reasonable answers, so both are offered, the user
picks). `live_graphs.py` is the second half: turning that exploration into
something that can actually run inside a live camera loop instead of
freezing on the first frame.
