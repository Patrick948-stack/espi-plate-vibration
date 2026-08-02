# ESPI Full Algorithm/capture_and_display.py - Live Capture and Display

## Purpose

This script connects to a Basler camera and opens two live windows:
1. Live Feed: raw frames directly from camera
2. Frame Subtraction: the absolute difference between consecutive frames, amplified to make vibrations visible

This lets users see both the raw camera image and a processed version that highlights changes frame-to-frame.

## How to Run

```bash
python capture_and_display.py
```

Or call it from another script:
```python
import capture_and_display as cad
cad.main(exposure_us=10000, gain_db=1.0, gain_factor=20)
```

Press 'q' to quit.

## Configuration

Default settings at the top of the file:

- `EXPOSURE_US`: How long the sensor captures light (in microseconds)
  - 10 milliseconds = 10,000 microseconds
  - Higher = brighter but slower frames
  
- `GAIN_DB`: Camera amplification in decibels
  - 0 dB = no extra gain
  - 6 dB = doubles brightness
  
- `GAIN_FACTOR`: Multiplier for the subtraction display
  - Controls how bright the vibration patterns appear
  - Higher = easier to see faint vibrations

## The main() Function

### What It Does

1. Connect to the first available Basler camera
2. If no camera found, print error and return
3. Configure camera:
   - Set manual exposure time (in microseconds)
   - Set gain level (in dB)
4. Create a live graph if requested (histogram, log histogram, or 3D)
5. Print instructions to user
6. Start the capture loop:
   - Grab frames continuously from camera
   - Display raw frame in "Live Feed" window
   - Update live graph (if enabled)
   - If we have a previous frame:
     - Calculate absolute difference between current and previous
     - Amplify the difference to make vibrations visible
     - Display amplified difference in "Frame Subtraction" window
   - Save current frame as previous for next iteration
   - Check for 'q' key press to quit
7. When done, stop camera, close all windows, close graph, disconnect camera

### Key Parameters

- `exposure_us`: Shutter time in microseconds
- `gain_db`: Camera gain in decibels
- `gain_factor`: Multiplier for difference image
- `graph_type`: Which graph to show ("histogram", "log_histogram", "3d", or None)

## How Frame Subtraction Works

The "Frame Subtraction" window shows what changed between one frame and the next:

1. Grab the current frame from camera
2. Calculate absolute difference: `difference = |current - previous|`
3. Multiply by gain_factor: `amplified = difference * gain_factor`
4. Clamp to 0-255 range (so values don't wrap)
5. Display the amplified result

**What you see:**
- Black areas: No change between frames
- Bright areas: Changed between frames (vibration)

**Why amplify:**
- Raw differences are often very small
- Amplifying makes vibration patterns visible
- gain_factor controls visibility (higher = more visible)

## Two Capture Windows

### Window 1: Live Feed

Shows the raw camera image:
- Gray background = scene
- Brighter areas = more light reflected
- Shows static scene + any vibrations

### Window 2: Frame Subtraction

Shows what changed frame-to-frame:
- Black = no change
- Bright = vibrating areas
- Helps visualize vibration patterns

### Optional Window 3: Live Graph

If graph_type is specified:
- "histogram": Bar chart of pixel intensity distribution
- "log_histogram": Histogram with logarithmic y-axis
- "3d": 3D surface plot of intensity across image

This helps understand the data and detect saturation or underexposure.

## Continuous Frame Grabbing

The script uses pylon's StartGrabbing() for continuous capture:

1. Call `camera.StartGrabbing(strategy)` to start streaming
2. In a loop, call `camera.RetrieveResult()` to get the latest frame
3. Process the frame (display, analyze, etc.)
4. Check for quit key
5. Call `camera.StopGrabbing()` when done

This is much faster than grabbing single frames one at a time.

## Error Handling

If frame grab fails:
1. Print error message
2. Suggest checking camera connection
3. Stop gracefully (don't crash with raw exception)

This often happens if the camera is disconnected or becomes unresponsive.

## Cleanup (The try/finally Block)

The `try/finally` block ensures that even if something goes wrong:
1. Stop camera grabbing
2. Destroy all OpenCV windows
3. Close the graph window (if any)
4. Disconnect the camera

This prevents the camera from being left in a locked state.

## Typical Usage

A user would:
1. Plug in a Basler camera
2. Run this script
3. See two windows with live feeds
4. Adjust camera position and lighting as needed
5. Press 'q' to quit
6. Use this script to verify camera and lighting setup before running experiments

## Related Files

- camera_control.py - Camera connection, settings, capture functions
- live_graphs.py - Creates the optional third graph window
- monitor.py - Command-line monitoring mode (calls this script)
- monitor_gui.py - PyQt6 GUI version with embedded capture
- capture_and_display_allied.py - Same thing but for Allied Vision cameras
- capture_and_display_cv2.py - Same thing but for USB webcams
