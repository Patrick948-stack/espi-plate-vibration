"""
camera_control.py
=================
A self-contained file with every camera function you need for ESPI experiments.

This file is completely independent — it does NOT import from any other file
in this project.  You can drop it into any folder and it will work as long as
pypylon, numpy, and opencv-python are installed.

HOW TO USE IN ANOTHER FILE
---------------------------
Option A — import only the functions you need:

    from camera_control import connect_camera, grab_single_frame, run_espi_pipeline

Option B — import everything under a short prefix:

    import camera_control as cam

    camera = cam.connect_camera()
    frame  = cam.grab_single_frame(camera)
    result = cam.run_espi_pipeline(reference_frame, frame)
    cam.disconnect_camera(camera)

Option C — import everything into your current file's namespace:

    from camera_control import *

    camera = connect_camera()   # no prefix needed

HOW THIS FILE IS ORGANIZED
---------------------------
  Section 1 — Camera Connection     : open and close the link to the camera
  Section 2 — Camera Settings       : exposure time, pixel format, read info
  Section 3 — Region of Interest    : crop the sensor to a smaller area
  Section 4 — Image Capture         : grab frames as numpy arrays
  Section 5 — ESPI Image Processing : subtract, amplify, threshold frames, average image
  Section 6 — Node Detection        : find nodal regions in difference images
  Section 7 — File Logging          : save images and session data to disk
  Section 8 — Quick View            : save an image as B&W and display it

DEPENDENCIES (install with pip if missing):
    pip install pypylon numpy opencv-python
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
# These are the only external libraries this file needs.
# All of them must be installed in your Python environment before using this file.
#
#   pypylon  — Basler's official Python SDK for controlling their cameras
#   numpy    — used to store image data as grids (arrays) of pixel values
#   cv2      — OpenCV: image processing, saving, and display
#   os       — file and folder path operations (built into Python, no install needed)
#   datetime — reading the current date/time (built into Python, no install needed)
# ==============================================================================
from __future__ import annotations

from pypylon import pylon
from pypylon import genicam
import numpy as np
import cv2
import os
from datetime import datetime


# ==============================================================================
# SECTION 1 — CAMERA CONNECTION
# ==============================================================================
# These are the FIRST and LAST functions you call in every camera session.
#
# Always follow this pattern:
#
#   camera = connect_camera()
#   if camera is None:
#       print("No camera found — stopping.")
#   else:
#       # ... do your work here ...
#       disconnect_camera(camera)
# ==============================================================================

def connect_camera():
    """
    Find the first available Basler camera, open it, and return it.

    Returns the camera object if successful, or None if no camera is found.

    The camera object is something you pass to every other function in this file.
    

    Example:
        camera = connect_camera()
        if camera is None:
            print("No camera found.")
    """
    try:
        # TlFactory scans all transport layers (USB3, GigE, etc.) and returns
        # the first detected camera device. Raises an exception if none found.
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()

        # Wrap the device in an InstantCamera — the high-level object used for
        # feature access, buffer management, and image grabbing.
        camera = pylon.InstantCamera(device)

        # Open the communication session. Must be called before accessing
        # any camera features or grabbing images.
        camera.Open()

        print(f"Connected to: {camera.GetDeviceInfo().GetModelName()}")
        return camera

    except genicam.GenericException as e:
        # Covers: no camera found, USB/GigE communication failure, etc.
        print(f"Could not connect to camera: {e}")
        return None


def disconnect_camera(camera):
    """
    Safely close the connection to the camera.

    Always call this when you are done — even if something went wrong earlier.
    If you skip this, the camera may stay in a locked state and refuse the
    next connection attempt until it is power-cycled.

    Example:
        disconnect_camera(camera)
    """
    try:
        # Stop any active grab loop before closing, so buffers are released cleanly.
        if camera.IsGrabbing():
            camera.StopGrabbing()

        # Close the communication session and free camera resources.
        camera.Close()
        print("Camera disconnected.")

    except genicam.GenericException as e:
        print(f"Error while disconnecting camera: {e}")


# ==============================================================================
# SECTION 2 — CAMERA SETTINGS
# ==============================================================================
# These functions control HOW the camera captures each frame.
#
# For ESPI measurements you almost always want:
#   • Manual exposure  (set_exposure_manual) — keeps brightness stable
#   • Mono8 pixel format (set_pixel_format)  — fast, enough bit depth
#
# After changing settings, call get_camera_info() to confirm they took effect.
# ==============================================================================

def set_exposure_manual(camera, exposure_us: float):
    """
    Turn off auto-exposure and lock the camera to a specific exposure time.

    Args:
        camera      : the camera object returned by connect_camera()
        exposure_us : exposure time in MICROSECONDS
                      (1 millisecond = 1 000 µs, 10 milliseconds = 10 000 µs)

    Returns the actual exposure time the camera accepted (may differ slightly
    from what you requested due to hardware rounding).

    Example:
        set_exposure_manual(camera, 10000)   # 10 ms exposure
    """
    # Disable auto exposure — required before ExposureTime.Value can be written.
    # Without this, the camera ignores the manual value.
    camera.ExposureAuto.Value = "Off"

    # Clamp the requested value to the hardware limits so we never write
    # a value the camera will reject with a GenICam exception.
    exposure_us = max(camera.ExposureTime.Min, min(exposure_us, camera.ExposureTime.Max))

    camera.ExposureTime.Value = exposure_us

    # Read back the value the camera actually accepted (may differ slightly
    # due to hardware increment rounding).
    actual = camera.ExposureTime.Value
    print(f"[Manual] Exposure set to: {actual} µs")
    return actual


def set_exposure_auto(camera):
    """
    Let the camera continuously adjust exposure to keep brightness at mid-grey.

    Useful during alignment when you just want to see something on screen.
    Do NOT use this during a measurement — changing brightness between the
    reference and live frames will corrupt the ESPI fringe pattern.

    Example:
        set_exposure_auto(camera)
    """
    # Give the auto algorithm the full hardware range to work within.
    camera.AutoExposureTimeLowerLimit.Value = camera.AutoExposureTimeLowerLimit.Min
    camera.AutoExposureTimeUpperLimit.Value = camera.AutoExposureTimeUpperLimit.Max

    # Target brightness 0.5 = mid-grey, a neutral default.
    camera.AutoTargetBrightness.Value = 0.5

    # Use ROI1 for brightness measurement so the algorithm focuses on the
    # center region rather than the full frame (default ROI position).
    camera.AutoFunctionROISelector.Value = "ROI1"
    camera.AutoFunctionROIUseBrightness.Value = True

    # "Continuous" — camera keeps adjusting exposure on every frame.
    camera.ExposureAuto.Value = "Continuous"
    print("[Auto] ExposureAuto set to Continuous.")


def set_gain_manual(camera, gain: float):
    """
    Turn off auto-gain and lock the camera to a specific gain value.

    Higher gain amplifies the sensor signal, making the image brighter —
    but also amplifies noise. For ESPI measurements, keep gain fixed so
    the noise level stays constant between the reference and live frames.

    Args:
        camera : the camera object returned by connect_camera()
        gain   : gain value in dB (typical range 0.0 – 24.0 for most Basler cameras)

    Returns the actual gain the camera accepted (may differ slightly due to
    hardware rounding).

    Example:
        set_gain_manual(camera, 10.0)   # 10 dB gain
    """
    camera.GainAuto.Value = "Off"

    gain = max(camera.Gain.Min, min(gain, camera.Gain.Max))
    camera.Gain.Value = gain

    actual = camera.Gain.Value
    print(f"[Manual] Gain set to: {actual} dB")
    return actual


def set_gain_auto(camera):
    """
    Let the camera continuously adjust gain to keep brightness at mid-grey.

    Useful during alignment when you just want to see something on screen.
    Do NOT use this during a measurement — changing gain between the
    reference and live frames will corrupt the ESPI fringe pattern.

    Example:
        set_gain_auto(camera)
    """
    camera.GainAuto.Value = "Continuous"
    print("[Auto] GainAuto set to Continuous.")


def set_pixel_format(camera, pixel_format: str) -> None:
    """
    Choose the data type used for each pixel.

    Common choices:
        "Mono8"  — 8-bit greyscale, values 0-255.    Fast, small files.
        "Mono12" — 12-bit greyscale, values 0-4095.  More detail, larger files.
        "RGB8"   — 8-bit colour.  Not normally used for ESPI.

    The camera must NOT be grabbing frames when you call this.

    Args:
        camera       : the camera object returned by connect_camera()
        pixel_format : a string like "Mono8" or "Mono12"

    Example:
        set_pixel_format(camera, "Mono8")
    """
    camera.PixelFormat.Value = pixel_format
    print(f"[set_pixel_format] Pixel format set to: {camera.PixelFormat.Value}")


def get_camera_info(camera):
    """
    Read the current camera settings and return them as a dictionary.

    Useful for checking settings and for passing to save_session_log().

    Returns a dict with keys:
        model, serial, width, height, exposure_us, exposure_auto, gain, pixel_format

    Example:
        info = get_camera_info(camera)
        print(info)
        # {'model': 'acA1920-40um', 'serial': '12345678', 'width': 1920, ...}
    """
    try:
        info = {
            "model":         camera.GetDeviceInfo().GetModelName(),
            "serial":        camera.GetDeviceInfo().GetSerialNumber(),
            "width":         camera.Width.Value,
            "height":        camera.Height.Value,
            "exposure_us":   camera.ExposureTime.Value,
            "exposure_auto": camera.ExposureAuto.Value,
            "gain":          camera.Gain.Value,
            "pixel_format":  camera.PixelFormat.Value,
        }
    except genicam.GenericException as e:
        print(f"Could not read one or more camera settings: {e}")
        info = {}
    return info


# ==============================================================================
# SECTION 3 — REGION OF INTEREST (ROI)
# ==============================================================================
# An ROI tells the camera to only read out a rectangular sub-area of the sensor.
#
# Why use an ROI?
#   • The camera transfers fewer pixels per frame  → higher frame rate
#   • Less data to store and process per frame
#
# The ROI is defined by its top-left corner (x, y) measured from the top-left
# of the full sensor, plus a width and height.
#
#   Full sensor (1920 × 1200):
#   +--------------------+
#   |                    |
#   |   (x,y)            |
#   |    +--------+      |
#   |    | ROI    |      |
#   |    |  w × h |      |
#   |    +--------+      |
#   +--------------------+
# ==============================================================================

def set_capture_roi(camera, x: int, y: int, width: int, height: int) -> None:
    """
    Restrict the camera to reading only a rectangular sub-area of the sensor.

    Args:
        camera : the camera object returned by connect_camera()
        x      : left edge of the ROI in pixels (measured from the sensor left)
        y      : top edge of the ROI in pixels  (measured from the sensor top)
        width  : width of the ROI in pixels
        height : height of the ROI in pixels

    All values are automatically clamped to the camera's hardware limits and
    aligned to the camera's increment grid — you cannot break the camera by
    passing an out-of-range value.

    Example:
        set_capture_roi(camera, x=256, y=256, width=512, height=512)
        # Camera now reads a 512×512 square starting 256 px from the top-left.
    """
    try:
        # Offsets must be set to 0 before changing Width/Height, otherwise
        # the new dimensions might push the ROI outside the sensor boundary.
        camera.OffsetX.Value = 0
        camera.OffsetY.Value = 0

        # Read the hardware limits and increment grids.
        cam_width  = camera.Width.Max
        cam_height = camera.Height.Max
        w_inc = camera.Width.Inc
        h_inc = camera.Height.Inc
        x_inc = camera.OffsetX.Inc
        y_inc = camera.OffsetY.Inc

        # Clamp and align width/height to the camera's increment grid.
        width  = max(camera.Width.Min,  min(width,  cam_width)  // w_inc * w_inc)
        height = max(camera.Height.Min, min(height, cam_height) // h_inc * h_inc)
        x      = min(x // x_inc * x_inc, cam_width  - width)
        y      = min(y // y_inc * y_inc, cam_height - height)

        camera.Width.Value   = width
        camera.Height.Value  = height
        camera.OffsetX.Value = x
        camera.OffsetY.Value = y

        print(f"[set_capture_roi] ROI set to x={x}, y={y}, w={width}, h={height}")

    except genicam.GenericException as e:
        print(f"[set_capture_roi] Error setting ROI: {e}")


def reset_capture_roi(camera) -> None:
    """
    Remove the ROI and go back to reading the full sensor.

    Call this before switching to a different ROI, or at the end of a session.

    Example:
        reset_capture_roi(camera)
    """
    try:
        # Offsets must be zeroed before restoring full Width/Height.
        camera.OffsetX.Value = 0
        camera.OffsetY.Value = 0
        camera.Width.Value   = camera.Width.Max
        camera.Height.Value  = camera.Height.Max

        print(f"[reset_capture_roi] ROI reset to full sensor "
              f"({camera.Width.Value} x {camera.Height.Value})")

    except genicam.GenericException as e:
        print(f"[reset_capture_roi] Error resetting ROI: {e}")


# ==============================================================================
# SECTION 4 — IMAGE CAPTURE
# ==============================================================================
# These functions pull image data off the camera into numpy arrays.
#
# A numpy array is a grid of numbers — for a Mono8 image it is a 2-D array
# of shape (height, width) where each value is 0 (black) to 255 (white).
#
# All three functions return None if the grab fails, so always check the
# return value before using it.
# ==============================================================================

def grab_single_frame(camera):
    """
    Grab exactly one frame from the camera and return it as a numpy array.

    Returns the frame as a numpy array, or None if the grab failed.

    The array shape is (height, width) for greyscale (Mono8 / Mono12).

    Example:
        frame = grab_single_frame(camera)
        if frame is not None:
            print(frame.shape)   # e.g. (1200, 1920)
    """
    try:
        # Grab exactly 1 frame then stop automatically.
        camera.StartGrabbingMax(1)

        # Block up to 5 seconds for the frame; raise on timeout.
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grabResult.GrabSucceeded():
            # .Array is a numpy ndarray — (H, W) for mono, (H, W, 3) for colour.
            frame = grabResult.Array.copy()
            grabResult.Release()
            return frame
        else:
            print(f"Grab failed: {grabResult.ErrorDescription}")
            grabResult.Release()
            return None

    except genicam.GenericException as e:
        print(f"Error grabbing single frame: {e}")
        return None


def grab_n_frames(camera, n: int):
    """
    Grab n frames in a row and return them as a list of numpy arrays.

    Each element in the list is one frame (numpy array).
    The list may be shorter than n if some frames fail to grab.

    Args:
        camera : the camera object returned by connect_camera()
        n      : how many frames to capture

    Example:
        frames = grab_n_frames(camera, 5)
        print(f"Got {len(frames)} frames")
    """
    frames = []
    try:
        camera.StartGrabbingMax(n)

        while camera.IsGrabbing():
            grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grabResult.GrabSucceeded():
                # Copy the array before releasing the buffer.
                frames.append(grabResult.Array.copy())
            else:
                print(f"Frame {len(frames) + 1} grab failed: {grabResult.ErrorDescription}")

            # Release the buffer back to the pool so acquisition can continue.
            grabResult.Release()

    except genicam.GenericException as e:
        print(f"Error grabbing frames: {e}")

    return frames


def grab_reference_frame(camera):
    """
    Grab one frame to use as the ESPI reference (zero-displacement baseline).

    In ESPI, the reference frame is captured BEFORE the object is excited.
    Every subsequent live frame is subtracted from this reference to reveal
    the interference pattern caused by vibration or deformation.

    Returns a numpy array, or None if the grab failed.

    Example:
        reference = grab_reference_frame(camera)
    """
    # Reuses grab_single_frame — a reference is just a captured frame that the
    # ESPI pipeline treats as the zero-displacement baseline.
    frame = grab_single_frame(camera)
    if frame is not None:
        print(f"Reference frame captured — shape: {frame.shape}, dtype: {frame.dtype}")
    return frame


# ==============================================================================
# SECTION 5 — ESPI IMAGE PROCESSING
# ==============================================================================
# These functions turn two camera frames into a visible fringe pattern.
#
# WHAT IS ESPI?
#   Electronic Speckle Pattern Interferometry (ESPI) works by capturing two
#   frames of the same object — one before excitation (reference) and one
#   during excitation (live).  Where the object has moved, the laser speckle
#   pattern shifts and the two frames look different.  Subtracting them reveals
#   fringes (bright/dark bands) that map the displacement field.
#
# TYPICAL PIPELINE:
#
#   reference = grab_reference_frame(camera)
#   live      = grab_single_frame(camera)
#
#   diff      = substract_frames(reference, live)   # Step 1: compute difference
#   amplified = amplify_difference(diff)             # Step 2: stretch contrast
#   binary, _ = binarize_diff(amplified)             # Step 3: threshold to mask
#
#   OR use the shortcut that does all three at once:
#
#   result = run_espi_pipeline(reference, live)
#   # result["colored"] is ready to save or display
# ==============================================================================

def substract_frames(previous: np.ndarray, current: np.ndarray) -> np.ndarray:
    """
    Compute the absolute pixel-wise difference between two frames.

    |frame_A - frame_B| is computed for every pixel.  The result is a
    greyscale image where bright pixels = large change, dark pixels = no change.

    Uses cv2.absdiff instead of simple subtraction to avoid overflow:
    with uint8 arrays, (10 - 20) wraps around to 246 in plain numpy,
    but cv2.absdiff correctly returns 10.

    Args:
        previous : first frame (numpy array, uint8 greyscale)
        current  : second frame (numpy array, uint8 greyscale, same shape)

    Returns a uint8 numpy array of the same shape.

    Example:
        diff = substract_frames(reference_frame, live_frame)
    """
    assert previous.shape == current.shape, (
        f"Frame shapes must match: {previous.shape} vs {current.shape}"
    )
    return cv2.absdiff(previous, current)


def amplify_difference(diff: np.ndarray) -> np.ndarray:
    """
    Stretch the contrast of a difference image so fringes are clearly visible.

    The raw difference image often has very small pixel values (dark overall)
    because most pixels changed only slightly.  This function rescales so the
    darkest pixel becomes 0 and the brightest becomes 255.

    Args:
        diff : greyscale difference image (numpy array, uint8)

    Returns a uint8 numpy array with the same shape, full contrast range.

    Example:
        amplified = amplify_difference(diff)
    """
    # NORM_MINMAX stretches the contrast so the interference pattern is
    # clearly visible even when raw pixel differences are small.
    amplified = cv2.normalize(
        src=diff,
        dst=None,
        alpha=0,
        beta=255,
        norm_type=cv2.NORM_MINMAX,
        dtype=cv2.CV_8U
    )
    return amplified


def binarize_diff(diff: np.ndarray, method: str = "otsu") -> tuple:
    """
    Threshold the difference image to produce a black-and-white mask.

    After amplification the image still has many grey levels.  Thresholding
    converts it to pure black (0) and white (255), making it easy to count
    or measure the fringe regions.

    Args:
        diff   : greyscale difference image (numpy array, uint8)
        method : how to pick the threshold value
                   "otsu"   — automatically finds the best threshold (recommended)
                   "manual" — always uses 127 as the threshold

    Returns a tuple: (binary_image, threshold_value)
        binary_image    : uint8 array — 255 = changed region, 0 = background
        threshold_value : the threshold number that was used (useful for logging)

    Example:
        binary, thresh = binarize_diff(amplified)
        print(f"Otsu threshold used: {thresh}")
    """
    if method == "otsu":
        # Otsu's algorithm finds the optimal threshold automatically by
        # minimising intra-class variance between foreground and background.
        thresh_val, binary = cv2.threshold(
            diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        thresh_val, binary = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)

    print(f"[binarize_diff] Threshold used: {thresh_val}")
    return binary, thresh_val


def show_diff(diff: np.ndarray, amplified: np.ndarray, binary: np.ndarray = None) -> None:
    """
    Display the difference images in OpenCV windows on screen.

    Opens up to three windows side by side:
        "Difference (raw)"       — the raw |A - B| image
        "Difference (amplified)" — contrast-stretched version
        "Binary Mask"            — black/white threshold (only if binary is given)

    Press any key on your keyboard to close all windows.

    Args:
        diff      : raw difference image (numpy array, uint8)
        amplified : contrast-stretched difference image (numpy array, uint8)
        binary    : optional black/white mask (numpy array, uint8)

    Example:
        show_diff(diff, amplified, binary)
    """
    cv2.imshow("Difference (raw)", diff)
    cv2.imshow("Difference (amplified)", amplified)
    if binary is not None:
        cv2.imshow("Binary Mask", binary)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def run_espi_pipeline(reference: np.ndarray, live: np.ndarray) -> dict:
    """
    Run the full ESPI pipeline on a reference and a live frame in one call.

    This is the shortcut function — it calls substract_frames,
    amplify_difference, and binarize_diff for you, then also applies a
    false-colour map so the fringe pattern is easy to read visually.

    Args:
        reference : the baseline frame grabbed before excitation
        live      : the frame grabbed during excitation

    Returns a dictionary with these keys:
        'diff'      — raw absolute difference image       (uint8 numpy array)
        'amplified' — contrast-stretched difference image (uint8 numpy array)
        'binary'    — Otsu-thresholded mask               (uint8 numpy array)
        'colored'   — false-colour amplified image        (uint8 BGR numpy array)
        'threshold' — the Otsu threshold value that was used (float)

    Example:
        result = run_espi_pipeline(reference_frame, live_frame)
        save_image(result["colored"], "output/fringe_pattern.png")
        show_diff(result["diff"], result["amplified"], result["binary"])
    """
    diff      = substract_frames(reference, live)
    amplified = amplify_difference(diff)
    binary, threshold = binarize_diff(amplified, method="otsu")

    # Apply a false-colour map so the fringe pattern is easier to read visually.
    # COLORMAP_JET: blue = low displacement, red = high displacement.
    colored = cv2.applyColorMap(amplified, cv2.COLORMAP_JET)

    return {
        "diff":      diff,
        "amplified": amplified,
        "binary":    binary,
        "colored":   colored,
        "threshold": threshold,
    }


def save_diff(diff: np.ndarray, path: str) -> bool:
    """
    Save a difference image to disk as a PNG file.

    Args:
        diff : the difference image to save (numpy array, uint8)
        path : full file path including filename, e.g. "output/diff_001.png"

    Returns True if saved successfully, False if it failed.

    Example:
        save_diff(result["amplified"], "output/amplified_001.png")
    """
    success = cv2.imwrite(path, diff)
    if success:
        print(f"[save_diff] Saved to: {path}")
    else:
        print(f"[save_diff] Failed to save to: {path}")
    return success

def average_img(img_list):
    """
    Computes the element-wise average of a list of uint8 image arrays.

    Parameters:
        img_list (list): A list of np.ndarray objects of the same shape (uint8).

    Returns:
        np.ndarray: The averaged image as a uint8 array, or None if the list is empty.
    """
    if len(img_list) == 0:
        print("[average_img] WARNING: received an empty list, returning None.")
        return None

    stacked = np.array(img_list, dtype=np.float32)
    mean_array = np.mean(stacked, axis=0)
    return np.round(mean_array).astype(np.uint8)

    

# ==============================================================================
# SECTION 6 — NODE DETECTION
# ==============================================================================
# These functions look at the binary mask produced by the ESPI pipeline and
# decide whether nodal regions are present.
#
# A NODE in a vibrating plate is a point or line that does NOT move.
# In an ESPI image, nodes appear as dark regions (small difference values)
# surrounded by bright fringe patterns.
#
# NOTE: detect_nodes() and has_nodes() are STUBS — the function bodies
# are not yet implemented.  The signatures and docstrings are written so
# you know exactly what each function is supposed to do and what arguments
# to pass once the implementation is added.
# ==============================================================================

def detect_nodes(diff: np.ndarray, treshold_method: str = "otsu") -> np.ndarray:
    """
    Apply thresholding to a difference image to isolate node regions.

    A node region is an area that did NOT move — it will have low pixel values
    in the difference image (close to black).

    Args:
        diff             : amplified difference image (uint8 greyscale numpy array)
        treshold_method  : "otsu" for automatic threshold, or "manual" for fixed

    Returns a binary numpy array: 255 = node region, 0 = background.

    NOTE: This function is not yet implemented.
    """
    # TODO: implement node detection logic
    pass


def has_nodes(binary: np.ndarray, min_area: int = 100) -> bool:
    """
    Return True if the binary image contains any node-like regions.

    This is a quick yes/no check — useful for filtering out noise before
    doing more detailed analysis.  Regions smaller than min_area pixels
    are ignored (they are most likely noise, not real nodes).

    Args:
        binary   : binary image from detect_nodes() (uint8 numpy array)
        min_area : minimum region size in pixels to count as a real node

    Returns True if at least one region larger than min_area exists.

    NOTE: This function is not yet implemented.
    """
    # TODO: implement connected-component area check
    pass


# ==============================================================================
# SECTION 7 — FILE LOGGING
# ==============================================================================
# These functions handle saving images and metadata to disk.
#
# Good logging makes experiments reproducible:
#   • build_filename()       → consistent, sortable filenames
#   • save_image()           → write numpy arrays to PNG or TIFF
#   • save_session_log()     → record camera settings to a text file
#   • log_frame_metadata()   → append per-frame data to a CSV spreadsheet
# ==============================================================================

def build_filename(frequency_hz: float, exposure_us: float, step: str,
                   extension: str = "png") -> str:
    """
    Build a sortable filename for one captured image.

    The format is:  <step>_<date>_<frequency>Hz_<exposure>us.<extension>

    Args:
        frequency_hz : the drive frequency for this frame, in Hz (e.g. 440.0)
        exposure_us  : the camera exposure time used, in microseconds
        step         : short description of the experimental step,
                       e.g. "bracing_added" (avoid spaces — use underscores)
        extension    : file extension WITHOUT the dot (default "png")

    Returns the filename as a string. This function only builds text;
    it doesn't creates or saves any file.

    Example:
        build_filename(440.0, 10000, "bracing_added")
        # Returns: "bracing_added_2026-06-10_00440.0Hz_010000us.png"
    """
    # datetime.now() gives a datetime OBJECT (not text). strftime() converts
    # it into a string using format codes: %Y = 4-digit year, %m = month,
    # %d = day. 
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Round to 6 decimal places to remove floating-point noise, then count how
    # many decimal places are actually needed for this frequency value.
    # Example: 170.225 needs 3; 440.0 needs 1; 170.27499999999998 rounds to
    # 170.275 and needs 3.  We use at least 1 so whole numbers still show "0.0".
    _cleaned = f"{round(frequency_hz, 6):.6f}".rstrip("0")
    _dec = len(_cleaned.split(".")[1]) if "." in _cleaned else 0
    _dec = max(1, _dec)
    _width = 5 + 1 + _dec  # 5 integer digits + dot + decimal digits, zero-padded
    freq_str = f"{frequency_hz:0{_width}.{_dec}f}"

    return f"{step}_{date_str}_{freq_str}Hz_{exposure_us:06.0f}us.{extension}"


def _resolve_output_dir(output_dir: str | None) -> str | None:
    """Return a safe output directory for image saves.

    Relative paths are resolved against the current working directory.
    Absolute paths are allowed when they are inside the user's home directory
    or the current working directory, or when they already exist.
    """
    if output_dir is None:
        return os.path.join(os.path.expanduser("~"), "Desktop")

    expanded = os.path.expanduser(output_dir)
    if not os.path.isabs(expanded):
        return os.path.abspath(expanded)

    abs_dir = os.path.abspath(expanded)
    home_dir = os.path.abspath(os.path.expanduser("~"))
    cwd_dir = os.path.abspath(os.getcwd())

    try:
        under_home = os.path.commonpath([home_dir, abs_dir]) == home_dir
        under_cwd = os.path.commonpath([cwd_dir, abs_dir]) == cwd_dir
    except ValueError:
        print(f"[save_image] Refusing to use output directory on a different drive: {abs_dir}")
        return None

    if not under_home and not under_cwd:
        print(f"[save_image] Refusing to create output directory outside home/current working directory: {abs_dir}")
        return None

    return abs_dir


def save_image(image: np.ndarray, output_dir: str = None, frequency_hz: float = 0.0,
               exposure_us: float = 0.0, step: str = "frame", bit_depth: str = "8bit") -> str | None:
    """
    Save a numpy array to disk, naming the file automatically with
    build_filename(). The output folder is created if it doesn't exist.
    If output_dir is not given (or is None), the image is saved to the
    user's Desktop instead.

    Args:
        image        : the image to save (a numpy array from the camera)
        output_dir   : folder to save into, e.g. output_dir = "C:/Users/Patrick/Desktop"                # straight to Desktop
        output_dir = "C:/Users/Patrick/Desktop" # inside My projects
        frequency_hz : drive frequency for this frame (goes into the name)
        exposure_us  : exposure time for this frame (goes into the name)
        step         : experimental step description (goes into the name)
        bit_depth    : "8bit"  → saves a PNG  (values 0–255)
                       "16bit" → saves a TIFF (values 0–65535, full precision)

    Returns the full path of the saved file, or None if saving failed.

    Example:
        path = save_image(frame, "output/", 440.0, 10000, "bracing_added")
    """
    try:
        output_dir = _resolve_output_dir(output_dir)
        if output_dir is None:
            return None

        # Choose the extension to MATCH the bit depth, so the filename and
        # the actual file format can never contradict each other.
        extension = "tiff" if bit_depth == "16bit" else "png"

        # Ask build_filename() to construct the name, then glue it onto the
        # folder with os.path.join(), which inserts the correct slash for
        # your operating system ("/" on Linux/Mac, "\" on Windows).

        filename = build_filename(frequency_hz, exposure_us, step, extension)
        filepath = os.path.join(output_dir, filename)

        # Create the output folder if it doesn't exist yet.
        # exist_ok=True means "don't crash if the folder is already there",
        # which lets us call this function many times in a loop safely.
        os.makedirs(output_dir, exist_ok=True)

        if bit_depth == "16bit":
            # Every numpy array has a dtype (the type of each pixel value).
            # TIFF needs the array to be uint16 to store 16-bit
            # data, so astype() converts a COPY to that type. This works
            # whether the camera handed us uint8 or uint16.
            img_16 = image.astype(np.uint16)
            success = cv2.imwrite(filepath, img_16)
        else:
            # 8-bit PNG — uint8 arrays save directly, no conversion needed.
            # cv2.imwrite figures out the format from the file extension.
            success = cv2.imwrite(filepath, image)

        # Quirk of OpenCV: imwrite returns True/False instead of raising an
        # error when it fails — so we must check the result ourselves.
        if success:
            print(f"[save_image] Saved: {filepath}")
            return filepath
        else:
            print(f"[save_image] cv2.imwrite failed for: {filepath}")
            return None

    except Exception as e:
        # Safety net: catch anything unexpected (bad permissions, corrupt
        # array, full disk...) so one bad save doesn't crash a long
        # acquisition run. We report the problem and return None.
        print(f"[save_image] Error saving to {output_dir}: {e}")
        return None

def save_session_log(session_info: dict, output_dir: str) -> None:
    """
    Write the camera settings to a human-readable text file.

    Creates a file named "session_log_<timestamp>.txt" inside output_dir.
    Pass the dictionary returned by get_camera_info() as session_info.

    Args:
        session_info : a dictionary of settings, e.g. from get_camera_info()
        output_dir   : folder where the log file will be written

    Example:
        info = get_camera_info(camera)
        save_session_log(info, "output/session_2026-06-10")
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(output_dir, f"session_log_{timestamp}.txt")

    with open(log_path, "w") as f:
        f.write(f"Session log — {timestamp}\n")
        f.write("=" * 40 + "\n")
        for key, value in session_info.items():
            f.write(f"{key}: {value}\n")

    print(f"[save_session_log] Log saved: {log_path}")


def log_frame_metadata(frame_index: int, exposure_us: float, mean_brightness: float, output_dir: str) -> None:
    """
    Append one row of per-frame data to a CSV file in output_dir.

    The CSV file is named "frame_metadata.csv".  On the first call it is
    created with a header row.  Every subsequent call appends a new row,
    so you can call this inside a frame-grabbing loop.

    Args:
        frame_index     : which frame this is (0, 1, 2, ...)
        exposure_us     : exposure time used for this frame in microseconds
        mean_brightness : average pixel value of the frame (0.0 to 255.0)
        output_dir      : folder where frame_metadata.csv will be written

    Example:
        import numpy as np
        for i, frame in enumerate(frames):
            brightness = float(np.mean(frame))
            log_frame_metadata(i, 10000, brightness, "output/")
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "frame_metadata.csv")

    # Write the header only when creating the file for the first time.
    write_header = not os.path.exists(csv_path)

    with open(csv_path, "a") as f:
        if write_header:
            f.write("frame_index,timestamp,exposure_us,mean_brightness\n")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        f.write(f"{frame_index},{timestamp},{exposure_us:.1f},{mean_brightness:.2f}\n")


# ==============================================================================
# SECTION 8 — QUICK VIEW
# ==============================================================================
# Use this when you want a one-liner that both saves and shows an image without
# having to call save_image() and cv2.imshow() separately.
#
# The image is always written as greyscale (black and white) regardless of
# whether the input is already mono or was captured in colour.
# ==============================================================================

def show_live_feed_from_camera(camera) -> None:
    """
    Show a live camera feed using a Basler camera handle you already have open.

    Grabs frames continuously with the LatestImageOnly strategy and displays
    them in a window.  Press 'e' to close the feed and return to the caller.

    Args:
        camera : the Basler camera object returned by connect_camera()

    Example:
        camera = connect_camera()
        show_live_feed_from_camera(camera)   # aim and focus, press 'e'
        set_exposure_manual(camera, 10000)   # now lock settings for measurement
    """
    print("Live feed open — aim the camera at the plate, then press 'e' to begin.")

    try:
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        while camera.IsGrabbing():
            grab_result = camera.RetrieveResult(
                5000, pylon.TimeoutHandling_ThrowException
            )

            if grab_result.GrabSucceeded():
                frame = grab_result.Array.copy()
                grab_result.Release()
                cv2.putText(
                    frame,
                    "Press 'e' to continue",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )
                cv2.imshow("ESPI Preview", frame)
            else:
                grab_result.Release()

            if cv2.waitKey(1) & 0xFF == ord("e"):
                break

    finally:
        camera.StopGrabbing()
        cv2.destroyWindow("ESPI Preview")


def save_and_display_img(image: np.ndarray, filename: str = None) -> str | None:
    """
    Convert an image to black and white, save it to the current working
    directory, and display it in a new window.

    If the image has colour channels it is converted to greyscale first.
    The window blocks until any key is pressed, then closes automatically.

    Args:
        image    : the image to process (numpy array, any shape / dtype)
        filename : optional filename with or without the .png extension.
                   If omitted, a timestamped name is generated automatically,
                   e.g. "bw_image_2026-06-15_14-30-00.png".

    Returns the full path of the saved file, or None if saving failed.

    Example:
        save_and_display_bw(frame)
        save_and_display_bw(frame, "result.png")
    """
    # Convert to greyscale if the array has a colour (third) dimension.
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"ref_image_{timestamp}.png"
    elif not filename.lower().endswith(".png"):
        filename += f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"

    filepath = os.path.join(os.getcwd(), filename)

    # Save before opening the display window so a write failure is caught early.
    success = cv2.imwrite(filepath, gray)
    if not success:
        print(f"[save_and_display_bw] Failed to save: {filepath}")
        return None
    print(f"[save_and_display_bw] Saved: {filepath}")

    # Open a named window so only this window is destroyed on key press,
    # leaving any other cv2 windows (e.g. show_diff) untouched.
    cv2.imshow("Reference Image", gray)
    cv2.waitKey(0)
    cv2.destroyWindow("Reference Image")

    return filepath


# ==============================================================================
# __all__ — WHAT GETS EXPORTED WITH "from camera_control import *"
# ==============================================================================
# This list controls which names are exported when someone writes:
#
#   from camera_control import *
#
# Only the names listed here are exported, keeping private variables like
# the datetime import from cluttering the caller's namespace.
# ==============================================================================
__all__ = [
    # Section 1: Connection
    "connect_camera",
    "disconnect_camera",

    # Section 2: Settings
    "set_exposure_manual",
    "set_exposure_auto",
    "set_gain_manual",
    "set_gain_auto",
    "set_pixel_format",
    "get_camera_info",

    # Section 3: ROI
    "set_capture_roi",
    "reset_capture_roi",

    # Section 4: Capture
    "grab_single_frame",
    "grab_n_frames",
    "grab_reference_frame",

    # Section 5: ESPI Processing
    "substract_frames",
    "amplify_difference",
    "binarize_diff",
    "show_diff",
    "run_espi_pipeline",
    "save_diff",
    "average_img",

    # Section 6: Node Detection
    "detect_nodes",
    "has_nodes",

    # Section 7: File Logging
    "build_filename",
    "save_image",
    "save_session_log",
    "log_frame_metadata",

    # Section 8: Live Feed
    "show_live_feed_from_camera",

    # Section 9: Quick View
    "save_and_display_img",
]
