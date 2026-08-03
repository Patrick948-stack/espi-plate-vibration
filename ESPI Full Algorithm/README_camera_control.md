# Camera Libraries: How to Use These Files

There are three camera library files in this folder. Each one is for a different type of camera hardware:

| File | Works with | Exposure unit |
|---|---|---|
| `camera_control.py` | Basler cameras (pypylon) | Microseconds: `10000` means 10 ms |
| `camera_control_inclusive.py` | Any USB camera or webcam (OpenCV) | OpenCV log₂ scale: `-6` is roughly 15 ms |
| `camera_control_allied_vision.py` | Allied Vision cameras (vmbpy) | Microseconds: `10000` means 10 ms |

All three files have the same function names and do the same things. The only differences are the hardware they talk to and the exposure unit. The pipeline files (`complete_pipeline_*.py`) use these internally, but you can also use them directly in your own scripts.

If you are running `run_experiment.py`, you never deal with exposure units yourself: you enter seconds and the conversion happens automatically.


## What is ESPI?

ESPI stands for Electronic Speckle Pattern Interferometry. The short version: you shine a laser on an object, vibrate it, and take photos. When you subtract two photos from each other, a pattern of light and dark rings appears wherever the surface moved. Those rings are called fringes and they show you the shape of the vibration.

These three files handle the camera side of that process: connecting, setting exposure and gain, grabbing frames, and doing the subtractions.


## Before you start: install what you need

```bash
pip install numpy opencv-python

# Basler cameras only:
pip install pypylon

# Allied Vision cameras only:
# Download vmbpy from https://github.com/alliedvision/VmbPy
# pip install <downloaded_wheel>.whl
```

| Package | What it is for |
|---|---|
| `pypylon` | Basler's official Python library |
| `vmbpy` | Allied Vision's Vimba X SDK |
| `numpy` | Stores images as grids of numbers you can do math on |
| `opencv-python` | Reads, processes, and saves image files |


## Quick start

**Basler camera**

```python
from camera_control import *

camera = connect_camera()
if camera is None:
    print("No camera found: check the USB cable.")
else:
    show_live_feed_from_camera(camera)    # aim the camera, press 'e' to close
    set_exposure_manual(camera, 10000)    # 10 ms
    set_gain_manual(camera, 0.0)          # 0 dB = no extra amplification

    frames = grab_n_frames(camera, 2)
    diff   = substract_frames(frames[0], frames[1])
    save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=10000, step="test")

    disconnect_camera(camera)
```

**Any USB camera or webcam**

```python
from camera_control_inclusive import *

camera = connect_camera(camera_index=0)  # 0 = the first camera the computer sees
if camera is None:
    print("No camera found: check the USB cable.")
else:
    show_live_feed_from_camera(camera)    # aim the camera, press 'e' to close
    discard_warmup_frames(camera, n=10)   # flush old frames from the buffer

    set_exposure_manual(camera, -6)       # -6 ≈ 15 ms in OpenCV's scale
    set_gain_manual(camera, 0.0)

    frames = grab_n_frames(camera, 2, max_retries=3)
    diff   = substract_frames(frames[0], frames[1])
    save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=-6, step="test")

    disconnect_camera(camera)
```

**Allied Vision camera**

```python
from camera_control_allied_vision import *

camera = connect_camera()
if camera is None:
    print("No camera found: check the connection.")
else:
    show_live_feed_from_camera(camera)    # aim the camera, press 'e' to close
    set_exposure_manual(camera, 10000)    # 10 ms in microseconds
    set_gain_manual(camera, 0.0)

    frames = grab_n_frames(camera, 2)
    diff   = substract_frames(frames[0], frames[1])
    save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=10000, step="test")

    disconnect_camera(camera)
```


## Function reference

### Section 1: Connecting and disconnecting

These are the first and last calls you make every time you use the camera.

| Function | Which files | What it does |
|---|---|---|
| `connect_camera()` | Basler, Allied Vision | Opens the camera and returns the camera object |
| `connect_camera(camera_index=0)` | USB/OpenCV only | Opens the camera at the given index (0 = first one found) |
| `disconnect_camera(camera)` | All three | Closes the connection cleanly |

If you forget to call `disconnect_camera`, the camera may refuse your next connection attempt until you unplug it. The pipeline files always call it inside a `finally` block so it runs even if something crashes during the sweep.

Basler and Allied Vision cameras save their pixel format (how many brightness levels each pixel can hold: "Mono8" for 0-255, "Mono12" for 0-4095) in the camera's own memory, so it carries over across reconnects and power cycles, no matter which program last touched it. Every image function in this project assumes "Mono8". `connect_camera()` now forces the camera into "Mono8" every time it connects, specifically so a camera left in some other format by another program (Vimba Viewer, pylon Viewer, an older script) can never silently make every picture in this project look far too dark.


### Section 2: Camera settings

| Function | What it does |
|---|---|
| `set_exposure_manual(camera, value)` | Locks exposure to a fixed value: use this for ESPI |
| `set_exposure_auto(camera)` | Lets the camera adjust brightness automatically |
| `set_gain_manual(camera, value)` | Locks gain to a fixed value: use this for ESPI |
| `set_gain_auto(camera)` | Lets the camera adjust gain automatically |
| `get_camera_info(camera)` | Returns the current settings as a dictionary |

**Exposure** is how long the sensor collects light. Longer = brighter, but moving objects will blur.

**Gain** is electronic amplification applied after the exposure. Higher = brighter, but also more noise (grain) in the image.

For ESPI, always use manual exposure and gain. If either one changes between frames, the subtraction will look wrong because the images will have different overall brightness.

**Exposure units explained**

| Library | Unit | Examples |
|---|---|---|
| `camera_control.py` | Microseconds | `10000` = 10 ms, `50000` = 50 ms |
| `camera_control_allied_vision.py` | Microseconds | Same |
| `camera_control_inclusive.py` | OpenCV log₂ scale | `-6` ≈ 15 ms |

The OpenCV log₂ scale is a quirk of how OpenCV stores exposure internally. Each step of 1 roughly doubles or halves the exposure time:

| OpenCV value | Approximate exposure |
|---|---|
| `-1` | ~500 ms (very bright: too long for most setups) |
| `-4` | ~62 ms |
| `-6` | ~15 ms (a reasonable starting point for ESPI) |
| `-8` | ~4 ms |
| `-11` | ~0.5 ms (very dark) |

When using `run_experiment.py` you always type seconds (like `0.01`). The program does the conversion for you.


### Section 3: Region of interest (ROI)

An ROI tells the camera to only read a rectangle of the full image. This speeds up capture and reduces file size: useful if your plate only fills part of the frame.

| Function | What it does |
|---|---|
| `set_capture_roi(camera, x, y, width, height)` | Sets a crop region |
| `reset_capture_roi(camera)` | Goes back to the full image |

```python
# Read only the centre 512x512 pixels of a 1920x1080 sensor
set_capture_roi(camera, x=704, y=284, width=512, height=512)
```

What x, y, width, height mean:

The top-left corner of the image is (0, 0). `x` is how many pixels from the left edge to where your rectangle starts. `y` is how many pixels from the top edge. `width` and `height` are the size of the rectangle. The function automatically clamps all values so the rectangle can never go outside the image bounds.


### Section 4: Capturing frames

These functions pull images from the camera as NumPy arrays. Each pixel is a number from 0 (black) to 255 (white).

| Function | What it does |
|---|---|
| `grab_single_frame(camera)` | Captures one image and returns it |
| `grab_n_frames(camera, n)` | Captures n images and returns them as a list |
| `grab_n_frames(camera, n, max_retries=3)` | Same, but retries automatically on failure (USB only) |
| `grab_reference_frame(camera)` | Captures the baseline image before vibration starts |
| `discard_warmup_frames(camera, n)` | Grabs and throws away n frames (USB only) |

All of these return `None` (or an empty list) if the grab fails. Always check:

```python
frame = grab_single_frame(camera)
if frame is None:
    print("Grab failed: check the camera connection.")
```

`discard_warmup_frames` matters for USB cameras because the camera buffer may still hold a few old frames from before you locked the exposure. Discarding around 10 frames ensures the new settings are actually active before you start measuring.


### Section 5: Live camera preview

All three camera libraries have a `show_live_feed_from_camera` function. It opens a window showing the live camera feed so you can aim and focus before starting a sweep.

| Function | Which files | What it does |
|---|---|---|
| `show_live_feed_from_camera(camera)` | All three | Shows live feed using the already-open camera handle |
| `show_live_camera()` | USB/OpenCV only | Opens a new camera connection just for the preview |

Press **`e`** to close the window and continue.

`show_live_feed_from_camera` is used in the pipelines instead of `show_live_camera` because opening a second connection to the same camera at the same time can cause conflicts on some operating systems.


### Section 6: Image processing

These functions turn two camera frames into an ESPI fringe image.

| Function | What it does |
|---|---|
| `substract_frames(frame_a, frame_b)` | Pixel-by-pixel absolute difference between two frames |
| `binarize_diff(diff)` | Converts the grey image to pure black and white |
| `average_img(list_of_images)` | Averages a list of images together to reduce noise |
| `run_espi_pipeline(reference, live, gain_factor=1.0)` | Does subtract + amplify (via gain_factor) + binarize all in one call |
| `show_diff(diff, amplified, binary)` | Opens preview windows on screen |
| `save_diff(diff, path)` | Saves a difference image to a file path |

**Why absolute difference and not regular subtraction?**

`substract_frames` uses `cv2.absdiff` rather than plain NumPy subtraction. The reason is uint8 overflow: in NumPy, `10 - 20` on a uint8 image wraps around to 246 instead of giving you 10. `absdiff` always gives you the true distance between two pixel values (10 in this example), which is what ESPI needs.

**Why average many frames?**

Each single difference image has random speckle noise mixed in with the real vibration pattern. Averaging many frames together cancels out the random noise while keeping the real pattern. More frames = cleaner result, but slower sweep.


### Section 7: Saving files

| Function | What it does |
|---|---|
| `build_filename(frequency_hz, exposure_us, step)` | Builds a consistent, sortable filename |
| `save_image(image, output_dir, frequency_hz, exposure_us, step)` | Saves an image with an auto-generated filename |
| `save_session_log(info, output_dir)` | Writes a text file with the camera settings |
| `log_frame_metadata(frame_index, exposure_us, brightness, output_dir)` | Adds a row to a CSV log file |

Filenames look like this:

```
espi_raw_2026-06-10_00170.2Hz_010000us.png
espi_raw_2026-06-10_000170.225Hz_010000us.png
```

The number of decimal places in the frequency adjusts automatically based on what the step size requires, so files always sort correctly by frequency in any file browser.


## Tips

**For dark images:** increase exposure time first, then try increasing gain. Longer exposure adds no noise; higher gain does.

**For blurry fringes:** try decreasing exposure. If the plate is moving fast and the shutter is open too long, the fringes blur together.

**Always use manual exposure and gain for ESPI.** Auto settings would change between frames and corrupt the subtraction.

**If `connect_camera()` returns None:**
1. Is the USB cable plugged in?
2. For Basler: is it in a USB 3.0 port (the blue one)? USB 2.0 is too slow.
3. For Basler: is Pylon Viewer open? Close it: only one program can use the camera at a time.
4. For Allied Vision: is Vimba X installed? Try importing `vmbpy` in Python to see if it errors.
5. For USB cameras: try a different index: `connect_camera(1)`, `connect_camera(2)`, etc.

**Always call `disconnect_camera` when you are done.** The pipeline files handle this automatically, but if you are writing your own script, put it in a `try/finally` block so it always runs even if your code crashes.


## Dependencies

```
numpy            pip install numpy
opencv-python    pip install opencv-python

pypylon          pip install pypylon                  (camera_control.py only)
vmbpy            install from wheel                   (camera_control_allied_vision.py only)
                 https://github.com/alliedvision/VmbPy
```

`os` and `datetime` come with Python: no install needed.
