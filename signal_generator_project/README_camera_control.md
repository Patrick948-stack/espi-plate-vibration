# camera_control.py — How to Use This File

This file gives you everything you need to communicate with a Basler camera from Python.
The file allows you to connect to the camera, adjust its settings, grab images, and process
them for ESPI experiments.

---

## What is ESPI (and why does this file exist)?

ESPI stands for Electronic Speckle Pattern Interferometry. In plain terms: you
shine a laser on an object, vibrate it, and take two photos at a given frequency. When you subtract the two photos, a pattern of bright
and dark rings appears wherever the object moved. Those patterns give you information about the way the object is vibrates.

This folder handles the camera side of that process, which include establishing the connection,
setting the exposure and gain, grabbing frames, and doing the subtraction math.

---

## Before You Start — Install These

Open a terminal and run:

```bash
pip install pypylon numpy opencv-python
```

| Package         | What it does                                                   |
| --------------- | -------------------------------------------------------------- |
| `pypylon`       | Basler's official Python library for controlling their cameras |
| `numpy`         | Stores image data as a grid of numbers you can do math on      |
| `opencv-python` | Reads, processes, and saves image files                        |

---

## How to Import This File

Pick whichever style you prefer:

**Option A — import only what you need:**

```python
from camera_control import connect_camera, grab_single_frame
```

**Option B — import everything with a short prefix:**

```python
import camera_control as cam

camera = cam.connect_camera()
frame  = cam.grab_single_frame(camera)
cam.disconnect_camera(camera)
```

**Option C — import everything directly into your file:**

```python
from camera_control import *

camera = connect_camera()   # no prefix needed
```

---

## Quick Start — The Shortest Useful Example

```python
from camera_control import *

# 1. Connect
camera = connect_camera()
if camera is None:
    print("No camera found. Check the USB cable.")
else:
    # 2. Set exposure and gain
    set_exposure_manual(camera, 10000)   # 10 milliseconds
    set_gain_manual(camera, 0.0)         # 0 dB = no amplification

    # 3. Grab a frame
    frame = grab_single_frame(camera)

    # 4. Save it
    save_image(frame, output_dir="/Users/yourname/Desktop/test_output")

    # 5. Disconnect
    disconnect_camera(camera)
```

---

## Quick Start — Running a Full ESPI Measurement

```python
from camera_control import *

camera = connect_camera()

set_exposure_manual(camera, 10000)
set_gain_manual(camera, 0.0)

reference = grab_reference_frame(camera)   # grab BEFORE exciting the object
live      = grab_single_frame(camera)      # grab DURING excitation

result = run_espi_pipeline(reference, live)
# result is a dictionary with keys: diff, amplified, binary, colored, threshold

save_image(result["colored"], output_dir="/Users/yourname/Desktop/output",
           frequency_hz=440.0, exposure_us=10000, step="plate_test")

disconnect_camera(camera)
```

---

## What's Inside — Section by Section

### Section 1 — Camera Connection

These are the first and last functions you call every time.

| Function                    | What it does                                                       |
| --------------------------- | ------------------------------------------------------------------ |
| `connect_camera()`          | Finds the first Basler camera, opens it, returns the camera object |
| `disconnect_camera(camera)` | Closes the connection cleanly — always call this when you're done  |

> If you forget to call `disconnect_camera`, the camera may lock up and refuse
> the next connection until you unplug and replug it.

---

### Section 2 — Camera Settings

Control how the camera captures each image.

| Function                                   | What it does                                                   |
| ------------------------------------------ | -------------------------------------------------------------- |
| `set_exposure_manual(camera, exposure_us)` | Locks the exposure to a fixed time (in microseconds)           |
| `set_exposure_auto(camera)`                | Lets the camera adjust brightness automatically                |
| `set_gain_manual(camera, gain)`            | Locks the gain to a fixed value in dB (0.0 = no amplification) |
| `set_gain_auto(camera)`                    | Lets the camera adjust gain automatically                      |
| `set_pixel_format(camera, "Mono8")`        | Sets whether the camera captures in greyscale or colour        |
| `get_camera_info(camera)`                  | Returns the current settings as a dictionary                   |

**Exposure** is how long the sensor collects light — longer exposure = brighter
image, but motion becomes blurry. **Gain** is electronic amplification — higher
gain = brighter image, but also more noise (graininess).

For ESPI measurements, always use **manual** exposure and **manual** gain.
If either setting changes between the reference frame and the live frame,
the subtraction result will be corrupted.

---

### Section 3 — Region of Interest (ROI)

An ROI tells the camera to only read a small rectangle of the sensor instead of
the full image. This makes the camera faster and produces smaller files.

| Function                                       | What it does                                     |
| ---------------------------------------------- | ------------------------------------------------ |
| `set_capture_roi(camera, x, y, width, height)` | Crops to a rectangle starting at position (x, y) |
| `reset_capture_roi(camera)`                    | Goes back to reading the full sensor             |

```python
# Read only the centre 512×512 pixels
set_capture_roi(camera, x=256, y=256, width=512, height=512)
```

---

### Section 4 — Image Capture

These functions pull images off the camera into Python as numpy arrays.
A numpy array is just a grid of numbers — for a greyscale image, each number
is a pixel brightness from 0 (black) to 255 (white).

| Function                       | What it does                                                                |
| ------------------------------ | --------------------------------------------------------------------------- |
| `grab_single_frame(camera)`    | Captures one image and returns it                                           |
| `grab_n_frames(camera, n)`     | Captures n images and returns them as a list                                |
| `grab_reference_frame(camera)` | Same as `grab_single_frame` — captures the baseline image before excitation |

All three return `None` if the grab fails, so it's good practice to check:

```python
frame = grab_single_frame(camera)
if frame is None:
    print("Something went wrong with the camera grab.")
```

---

### Section 5 — ESPI Image Processing

These functions do the maths that turns two camera frames into a fringe pattern.

| Function                             | What it does                                                         |
| ------------------------------------ | -------------------------------------------------------------------- |
| `substract_frames(frame_a, frame_b)` | Calculates the absolute difference between two frames pixel-by-pixel |
| `amplify_difference(diff)`           | Stretches the contrast so faint fringes become visible               |
| `binarize_diff(diff)`                | Converts the grey image to pure black and white                      |
| `show_diff(diff, amplified, binary)` | Opens windows on screen to preview the images                        |
| `run_espi_pipeline(reference, live)` | Does all of the above in one call — returns a dictionary of results  |
| `save_diff(diff, path)`              | Saves a difference image to a file path you specify                  |
| `average_img(list_of_images)`        | Averages a list of images together to reduce noise                   |

**Why do we subtract two frames?**
When you shine a laser on a vibrating plate, the speckle pattern (the grainy
laser texture) shifts where the plate moved. Subtracting the before-image from
the after-image cancels out everything that stayed still — only the moved regions
remain as bright areas. Those bright regions form the fringe pattern.

---

### Section 6 — Node Detection

Nodes are points on a vibrating plate that don't move at all. In an ESPI image,
they appear as dark spots surrounded by bright fringes.

| Function             | What it does                                            |
| -------------------- | ------------------------------------------------------- |
| `detect_nodes(diff)` | Finds node regions in a difference image                |
| `has_nodes(binary)`  | Returns True/False — does this image contain any nodes? |

> **Note:** These two functions are not yet implemented. The structure is in
> place — they just need their logic written inside.

---

### Section 7 — File Logging

These functions handle saving images and experiment records to disk.

| Function                                                               | What it does                                                   |
| ---------------------------------------------------------------------- | -------------------------------------------------------------- |
| `build_filename(frequency_hz, exposure_us, step)`                      | Builds a consistent, sortable filename (doesn't save anything) |
| `save_image(image, output_dir, ...)`                                   | Saves an image to a folder with an auto-generated name         |
| `save_session_log(info, output_dir)`                                   | Writes camera settings to a text file                          |
| `log_frame_metadata(frame_index, exposure_us, brightness, output_dir)` | Appends one row to a CSV file — useful inside a capture loop   |

**Filename format:**

```
bracing_added_2026-06-10_00440.0Hz_010000us.png
```

The date and numbers are zero-padded so files sort correctly in any file browser.

---

## Tips

- **Always call `disconnect_camera` at the end**, even if something went wrong.
  The pipeline (`complete_pipeline.py`) does this automatically for you.

- **For dark images:** increase `exposure_us` first, then `gain` if you need more.
  Prefer longer exposure over high gain — gain adds noise, exposure doesn't.

- **For the pipeline to work correctly**, both the reference frame and the live
  frame must be captured with the exact same exposure and gain. Use the manual
  functions, not the auto ones.

- **If `connect_camera()` returns None**, check:
  1. Is the USB cable plugged in?
  2. Is it plugged into a USB 3.0 port? (The blue port — USB 2.0 is too slow.)
  3. Is Pylon Viewer open? Close it — only one program can talk to the camera at once.

---

## Dependencies Summary

```
pypylon          — pip install pypylon
numpy            — pip install numpy
opencv-python    — pip install opencv-python
```

Everything else (`os`, `datetime`) comes with Python — no install needed.
