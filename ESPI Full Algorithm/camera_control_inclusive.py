"""
camera_control_inclusive.py
===========================
A replacement for camera_control.py that works with any camera
your computer can see (the previous version only worked for Basler cameras): webcams, USB cameras, GigE cameras, etc.

Author: Patrick Mulikuza

  * camera_control.py only works with Basler cameras (using Basler pypylon library)
  * camera_control_inclusive.py works with any camera (only needs opencv-python)

Every function has the same name and the same arguments as camera_control.py,
so you can swap the import line in your scripts and everything else stays the
same.  Just change:

    from camera_control import *          ← Basler only

to:

    from camera_control_inclusive import *   ← any camera

LIMITATIONS of camera_control_inclusive.py compated to camera_control.py
--------------------------------------------------------------------------
Because OpenCV talks to cameras through the operating system rather than
a dedicated SDK, some settings are less precise or not available at all:

  Exposure    : not in microseconds.  OpenCV uses its own scale (usually
                log2 on most cameras).
                Not all cameras let OpenCV control exposure.

  Gain        : Works on many cameras, silently ignored on others.

  Pixel format: NOT controllable through OpenCV.  The camera delivers
                whatever format it defaults to.  set_pixel_format() will
                print a message but do nothing.

  ROI         : OpenCV cannot tell the camera to read only part of the sensor
                (hardware ROI).  Instead we apply a SOFTWARE crop after the
                full frame arrives.  The result looks the same but the
                camera still reads the full sensor, so frame rate does NOT
                improve the way it does with a real hardware ROI.

HOW THIS FILE IS ORGANIZED
---------------------------
  Section 1 — Camera Connection     : open and close the link to the camera
  Section 2 — Camera Settings       : exposure, gain, pixel format, info
  Section 3 — Region of Interest    : software crop to a smaller area
  Section 4 — Image Capture         : grab frames as numpy arrays
  Section 5 — ESPI Image Processing : subtract, amplify, threshold, average
  Section 6 — Node Detection        : find nodal regions in difference images
  Section 7 — File Logging          : save images and session data to disk
  Section 8 — Quick View            : save an image as B&W and display it
  Section 9 — Live Feed & Capture   : live camera window and multi-photo capture

DEPENDENCIES (install with pip if missing):
    pip install numpy opencv-python matplotlib
"""

from __future__ import annotations

import cv2
import numpy as np
import os
import tempfile
from datetime import datetime
from matplotlib import pyplot as plt


# ==============================================================================
# INTERNAL ROI STORE
# ==============================================================================
# OpenCV does not support hardware ROI, so we store the desired crop region
# here and apply it manually every time a frame is grabbed.
# This _roi_store dictionary maps id(camera) → (x, y, width, height).
# When no ROI is set for a camera, its id is simply not in this dict. 
# id(camera) returns a unique integer memory address of the camera

# ==============================================================================
_roi_store = {}


def _apply_roi(frame, camera):
    """
    Internal helper — crops a frame to the stored ROI for this camera.
    Returns the full frame unchanged if no ROI has been set.
    """
    roi = _roi_store.get(id(camera)) # looks up the key (id(camera)), returns the value (x,y,w,h) if key exsists, and not if it doesn't
    if roi is None:
        return frame
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]


# ==============================================================================
# SECTION 1 — CAMERA CONNECTION
# ==============================================================================
# These are the FIRST and LAST functions you call in every camera session.
#
# The pattern is exactly the same as camera_control.py:
#
#   camera = connect_camera()
#   if camera is None:
#       print("No camera found — stopping.")
#   else:
#       # ... do your work here ...
#       disconnect_camera(camera)
#
# The only difference: connect_camera() accepts an optional camera_index so
# you can choose which camera to open when more than one is plugged in.
# Index 0 is the first camera the computer finds (the default).
# ==============================================================================

def connect_camera(camera_index: int = 0):
    """
    Open a camera by its index number and return it.

    camera_index = 0 means "use the first camera the computer finds."
    If you have more than one camera and it opens the wrong one, try 1, 2, etc.

    Returns the camera object if successful, or None if no camera is found.

    Example:
        camera = connect_camera()        # opens first camera
        camera = connect_camera(1)       # opens second camera
        if camera is None:
            print("No camera found.")
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Could not open camera at index {camera_index}.")
        print("Things to try:")
        print("  - Is a camera plugged in?")
        print("  - Try connect_camera(1) or connect_camera(2)")
        return None

    # Read one property to confirm the camera is actually delivering frames.
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Connected to camera {camera_index}  ({width} x {height} px)")
    return cap


def disconnect_camera(camera):
    """
    Safely close the connection to the camera.

    Always call this when you are done, even if something went wrong earlier.
    If you skip this, the camera may stay locked and refuse to connect next time.

    Example:
        disconnect_camera(camera)
    """
    # Also clear any stored ROI for this camera so memory doesn't accumulate. 
    # id returns the unique identification number of the camera, 
    # which the pop method searches for in the dictionary, 
    # if it's found, pop returns its value, if not, it returns None
    _roi_store.pop(id(camera), None)

    camera.release()
    print("Camera disconnected.")


# ==============================================================================
# SECTION 2 — CAMERA SETTINGS
# ==============================================================================
# These functions control HOW the camera captures each frame.
#
# IMPORTANT DIFFERENCE FROM camera_control.py:
#   The Basler SDK lets you set exposure in exact microseconds.
#   OpenCV uses whatever scale the camera driver uses,
#   which is usually a log2 scale (e.g. -6 ≈ 15 ms on many webcams).
#   See set_exposure_manual() for more detail.
#
# After changing settings, call get_camera_info() to confirm they took effect.
# ==============================================================================

def set_exposure_manual(camera, exposure_value: float):
    """
    Turn off auto-exposure and lock the camera to a specific exposure value.
    LOGIC:
    1. Turn off auto-exposure (let us control it manually)
    2. Set the exposure we want
    3. Read back what the camera actually accepted


    IMPORTANT: The exposure value here is NOT in microseconds.
    OpenCV passes whatever number you give straight to the camera driver,
    which usually interprets it on a log2 scale:
        -1  ≈ very bright  (long exposure)
        -6  ≈ medium        (good starting point)
        -11 ≈ very dark     (short exposure)
    The exact meaning depends on your camera, so experiment to find what works.

    Not all cameras let OpenCV control exposure.  If the image brightness
    doesn't change when you call this, it might mean that your camera driver 
    does not support it.

    Args:
        camera         : the camera object returned by connect_camera()
        exposure_value : exposure setting to pass to OpenCV (NOT microseconds)

    Example:
        set_exposure_manual(camera, -6)   
    """
    # Value 1 = manual exposure mode on most camera drivers. 
    # Value 3 =	Auto-exposure ON
    camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    camera.set(cv2.CAP_PROP_EXPOSURE, exposure_value)

    actual = camera.get(cv2.CAP_PROP_EXPOSURE)
    print(f"[Manual] Exposure set to: {actual}  (requested: {exposure_value})")
    return actual


def set_exposure_auto(camera):
    """
    Let the camera adjust exposure automatically.

    Useful during alignment when you just want to see something on screen.
    Do NOT use this during a measurement since changing brightness between frames
    might corrupt the ESPI fringe pattern.

    Example:
        set_exposure_auto(camera)
    """
    # Value 3 = auto exposure mode on most camera drivers.
    camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
    print("[Auto] Exposure set to automatic.")


def set_gain_manual(camera, gain: float):
    """
    Lock the camera to a specific gain value.

    Higher gain makes the image brighter but also amplifies noise.
    For ESPI measurements, keep gain fixed so noise stays constant between frames.

    Gain values vary by camera. Typically, 0.0  means no amplification.
    Not all cameras let OpenCV control gain; this function might be silently ignored by devices.

    Args:
        camera : the camera object returned by connect_camera()
        gain   : gain value (camera-dependent scale)

    Example:
        set_gain_manual(camera, 0.0)
    """
    camera.set(cv2.CAP_PROP_GAIN, gain)

    actual = camera.get(cv2.CAP_PROP_GAIN)
    print(f"[Manual] Gain set to: {actual}  (requested: {gain})")
    return actual


def set_gain_auto(camera):
    """
    Let the camera adjust gain automatically.

    NOTE: OpenCV does not have a universal auto-gain command.
    This function resets gain to 0, which tells most cameras to stop
    applying manual amplification.  Full auto-gain is not reliably
    available through OpenCV, use this function with caution.

    Example:
        set_gain_auto(camera)
    """
    camera.set(cv2.CAP_PROP_GAIN, 0)
    print("[Auto] Gain reset to 0 (auto-gain not universally supported in OpenCV).")


def set_pixel_format(camera, pixel_format: str) -> None:
    """
    NOT SUPPORTED in this file.

    OpenCV does not let you choose the pixel format. The camera delivers
    whatever format it defaults to, and OpenCV converts it to BGR internally.
    Frames returned by grab functions in this file are always converted to
    greyscale (8-bit, values 0–255) to match camera_control.py behaviour.

    This function exists only so code written for camera_control.py doesn't
    crash when you swap to this file.  It prints a message and does nothing.

    Example:
        set_pixel_format(camera, "Mono8")
        # Prints a notice and returns — no change is made.
    """
    print(f"[set_pixel_format] NOTE: pixel format cannot be set through OpenCV.")
    print(f"  Frames are always returned as 8-bit greyscale in this file.")


def get_camera_info(camera):
    """
    Read the current camera settings and return them as a dictionary.

    Useful for checking settings and for passing to save_session_log().

    Returns a dict with keys:
        camera_index, width, height, fps, exposure, gain, brightness

    NOTE: Some cameras report 0 or -1 for settings they do not expose
    through OpenCV.  It just means the driver does not
    share that information with OpenCV.

    Example:
        info = get_camera_info(camera)
        print(info)
    """
    info = {
        "width":      int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height":     int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps":        camera.get(cv2.CAP_PROP_FPS),
        "exposure":   camera.get(cv2.CAP_PROP_EXPOSURE),
        "gain":       camera.get(cv2.CAP_PROP_GAIN),
        "brightness": camera.get(cv2.CAP_PROP_BRIGHTNESS),
    }
    return info


# ==============================================================================
# SECTION 3 — REGION OF INTEREST (ROI)
# ==============================================================================
# An ROI restricts capture to a rectangular sub-area of the frame.
#
# IMPORTANT DIFFERENCE FROM camera_control.py:
#   camera_control.py tells the Basler camera hardware to only read part of
#   the sensor, so fewer pixels travel over the USB cable, giving a higher
#   frame rate.
#
#   This file cannot do that.  OpenCV always reads the full frame from the
#   camera and we crop the numpy array afterwards in software.  The result
#   looks the same, but the frame rate does not improve.
#
#   The ROI is stored in memory (see _roi_store at the top of this file) and
#   applied automatically inside every grab function.
# ==============================================================================

def set_capture_roi(camera, x: int, y: int, width: int, height: int) -> None:
    """
    Tell the grab functions to crop every frame to a rectangular sub-area.

    This is a SOFTWARE crop — the full sensor is still read every frame.
    The result looks the same as a hardware ROI but frame rate is unchanged.

    Args:
        camera : the camera object returned by connect_camera()
        x      : left edge of the crop in pixels (from the left of the frame)
        y      : top edge of the crop in pixels  (from the top of the frame)
        width  : width of the crop in pixels
        height : height of the crop in pixels

    Values are automatically clamped so the crop never goes outside the frame.

    Example:
        set_capture_roi(camera, x=256, y=256, width=512, height=512)
    """
    # Find out how big the camera image is
    frame_w = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Clamp everything so the crop can never reach outside the actual frame. 
    # if the value is too small, push it up to the minimum; if it's too big, 
    # pull it down to the maximum.
    x      = max(0, min(x, frame_w - 1))
    y      = max(0, min(y, frame_h - 1))
    width  = max(1, min(width,  frame_w - x))
    height = max(1, min(height, frame_h - y))

    _roi_store[id(camera)] = (x, y, width, height)
    print(f"[set_capture_roi] Software ROI set to x={x}, y={y}, w={width}, h={height}")
    print(f"  (Note: full frame is still read from the sensor — frame rate unchanged.)")


def reset_capture_roi(camera) -> None:
    """
    Remove the crop and go back to receiving the full frame.

    Call this before switching to a different ROI, or at the end of a session.

    Example:
        reset_capture_roi(camera)
    """
    _roi_store.pop(id(camera), None)

    w = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[reset_capture_roi] ROI cleared — full frame restored ({w} x {h})")


# ==============================================================================
# SECTION 4 — IMAGE CAPTURE
# ==============================================================================
# These functions pull image data off the camera into numpy arrays.
#
# A numpy array is a grid of numbers. For an 8-bit greyscale image it is a
# 2-D array of shape (height, width) where each value is 0 (black) to 255 (white).
#
# OpenCV reads colour cameras as BGR (3-channel).  All functions here convert
# to greyscale automatically so the output matches camera_control.py.
#
# All three functions return None if the grab fails, so always check the
# return value before using it.
# ==============================================================================

def grab_single_frame(camera):
    """
    Grab exactly one frame from the camera and return it as a numpy array.

    Returns the frame as a numpy array (height × width, greyscale), or None
    if the grab failed.

    Example:
        frame = grab_single_frame(camera)
        if frame is not None:
            print(frame.shape)   # e.g. (480, 640)
    """
    ok, frame = camera.read()

    if not ok or frame is None:
        print("Grab failed — camera did not return a frame.")
        return None

    # OpenCV colour cameras give a 3-channel BGR image.
    # We convert to greyscale so the output is a simple 2-D array,
    # exactly like the Mono8 frames from the Basler camera.
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply software ROI crop if one has been set.
    frame = _apply_roi(frame, camera)

    return frame


def grab_single_frame_color(camera):
    """
    Grab exactly one frame, but skip the greyscale reduction grab_single_frame()
    performs, so callers that need the real color data can have it.

    grab_single_frame() always converts a color frame down to a 2D greyscale
    array, since that is the contract monitor.py, capture_and_display*.py,
    and run_experiment.py all rely on. monitor_gui.py's single-channel R/G/B
    extraction needs the original 3-channel BGR frame before that reduction
    happens, or every extraction method returns the same already-flattened
    value no matter which color channel or backend was picked. This function
    exists so that code path can get the frame it actually needs, without
    changing what grab_single_frame() returns for anyone else.

    Returns a (height, width, 3) BGR array for a color camera, a (height,
    width) array for a camera that is already greyscale, or None if the grab
    failed.

    Example:
        frame = grab_single_frame_color(camera)
        if frame is not None:
            print(frame.shape)   # e.g. (480, 640, 3) for a color camera
    """
    ok, frame = camera.read()

    if not ok or frame is None:
        print("Grab failed, camera did not return a frame.")
        return None

    # Apply software ROI crop if one has been set. No greyscale reduction
    # here, unlike grab_single_frame().
    frame = _apply_roi(frame, camera)

    return frame


def grab_single_frame_with_retry(camera, max_retries: int = 3):
    """
    Like grab_single_frame(), but tries again if the first attempt fails.

    Some cameras occasionally drop a frame, especially over USB when the
    computer is busy.  Retrying a couple of times gives us a second chance
    without aborting the whole experiment.

    Args:
        camera      : the camera object returned by connect_camera()
        max_retries : how many total attempts to make before giving up.
                      Defaults to 3 (one try + two retries).

    Returns the first successful frame as a numpy array, or None if every
    attempt failed.

    Example:
        frame = grab_single_frame_with_retry(camera, max_retries=3)
    """
    for attempt in range(max_retries):
        ok, raw = camera.read()

        if ok and raw is not None:
            if raw.ndim == 3:
                raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            return _apply_roi(raw, camera)

        if attempt < max_retries - 1:
            print(f"  Frame grab failed — retrying "
                  f"({attempt + 2}/{max_retries})...")

    print(f"  Frame grab failed after {max_retries} attempt(s).")
    return None


def grab_n_frames(camera, n: int, max_retries: int = 3):
    """
    Grab n frames in a row and return them as a list of numpy arrays.

    Each element in the list is one frame (numpy array).
    The list may be shorter than n if some frames fail to grab even after
    retrying max_retries times.

    Args:
        camera      : the camera object returned by connect_camera()
        n           : how many frames to capture
        max_retries : how many attempts per frame before giving up.
                      Defaults to 3.

    Example:
        frames = grab_n_frames(camera, 5)
        print(f"Got {len(frames)} frames")
    """
    frames = []

    for _ in range(n):
        frame = grab_single_frame_with_retry(camera, max_retries=max_retries)

        if frame is None:
            continue

        frames.append(frame)

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
    frame = grab_single_frame(camera)
    if frame is not None:
        print(f"Reference frame captured — shape: {frame.shape}, dtype: {frame.dtype}")
    return frame


def discard_warmup_frames(camera, n: int = 5):
    """
    Read and throw away the first n frames from the camera.
    When you first open a camera — or after changing the exposure or gain — 
    the camera sensor doesn't respond to the new settings instantly. 
    The first few frames it delivers may still have the old brightness. 
    Calling this function reads and discards those stale frames so that 
    by the time you start capturing real data, the sensor has fully settled.

    A good rule of thumb: discard at least 5 frames after opening the camera, 
    and at least 3 more after changing the exposure.

    Args:
        camera : the camera object returned by connect_camera()
        n : how many frames to throw away. Defaults to 5.
    """
    print(f"Discarding {n} warmup frame(s) so the sensor can settle...")
    discarded = 0
    for _ in range(n):
        ok, _ = camera.read()
        if ok:
            discarded += 1
        else:
            print("Warning: Camera read failed or disconnected during warmup.")
            break  # Stop trying to read frames if the camera errors out
            
    print(f" Done — {discarded}/{n} warmup frames cleared.")



# ==============================================================================
# SECTION 5 — ESPI IMAGE PROCESSING
# ==============================================================================
# These functions are IDENTICAL to camera_control.py.
# They only work on numpy arrays regardless of the camera that produced them.
# No changes are needed here.
#
# TYPICAL PIPELINE:
#
#   frame_a = grab_single_frame(camera)   # first frame
#   frame_b = grab_single_frame(camera)   # second frame (plate has moved slightly)
#
#   diff      = substract_frames(frame_a, frame_b)   # Step 1: difference
#   amplified = amplify_difference(diff)              # Step 2: stretch contrast
#   binary, _ = binarize_diff(amplified)              # Step 3: threshold to mask
#
#   OR use the shortcut that does all three at once:
#
#   result = run_espi_pipeline(frame_a, frame_b)
#   # result["colored"] is ready to save or display
# ==============================================================================

def substract_frames(previous: np.ndarray, current: np.ndarray):
    """
    Compute the absolute pixel-wise difference between two frames.

    |frame_A - frame_B| is computed for every pixel.  Bright pixels in the
    result mean the plate moved a lot there; dark pixels mean it stayed still.

    Uses cv2.absdiff instead of plain subtraction to avoid uint8 overflow:
    plain numpy would wrap (10 - 20) around to 246, but absdiff returns 10.

    Args:
        previous : first frame  (numpy array, uint8 greyscale)
        current  : second frame (numpy array, uint8 greyscale, same shape)

    Returns a uint8 numpy array of the same shape, or None if the frames
    have different sizes (which would make subtraction meaningless).

    Example:
        diff = substract_frames(frame_a, frame_b)
        if diff is None:
            print("Frame size mismatch — skipping this pair.")
    """
    if previous.shape != current.shape:
        print(f"[substract_frames] Frame sizes don't match "
              f"({previous.shape} vs {current.shape}) — returning None.")
        return None
    return cv2.absdiff(previous, current)


def amplify_difference(diff: np.ndarray) -> np.ndarray:
    """
    Stretch the contrast of a difference image so fringes are clearly visible.

    The raw difference image is usually very dark because most pixels changed
    only slightly.  This function rescales so the darkest pixel becomes 0 and
    the brightest becomes 255 — making the fringe pattern easy to see.

    Args:
        diff : greyscale difference image (numpy array, uint8)

    Returns a uint8 numpy array with the same shape, full contrast range.

    Example:
        amplified = amplify_difference(diff)
    """
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

    Example:
        binary, thresh = binarize_diff(amplified)
        print(f"Threshold used: {thresh}")
    """
    if method == "otsu":
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

    Opens up to three windows:
        "Difference (raw)"       — the raw |A - B| image
        "Difference (amplified)" — contrast-stretched version
        "Binary Mask"            — black/white threshold (only if binary is given)

    Press any key to close all windows.

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
    Run the full ESPI pipeline on two frames in one call.

    Calls substract_frames, amplify_difference, and binarize_diff for you,
    then also applies a false-colour map so the fringe pattern is easy to read.

    Args:
        reference : first frame (or baseline frame)
        live      : second frame (captured slightly later)

    Returns a dictionary with keys:
        'diff'      — raw absolute difference image       (uint8 numpy array)
        'amplified' — contrast-stretched difference image (uint8 numpy array)
        'binary'    — Otsu-thresholded mask               (uint8 numpy array)
        'colored'   — false-colour amplified image        (uint8 BGR numpy array)
        'threshold' — the Otsu threshold value that was used (float)

    Example:
        result = run_espi_pipeline(frame_a, frame_b)
        save_image(result["colored"], "output/fringe_pattern.png")
    """
    diff      = substract_frames(reference, live)
    amplified = amplify_difference(diff)
    binary, threshold = binarize_diff(amplified, method="otsu")

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
    Compute the element-wise average of a list of images.

    Each image must be a numpy array of the same shape.
    The result is rounded back to uint8 (values 0–255).

    Args:
        img_list : list of numpy arrays (all the same shape, uint8)

    Returns the averaged image as a uint8 array, or None if the list is empty.

    Example:
        averaged = average_img(list_of_difference_images)
    """
    if len(img_list) == 0:
        print("[average_img] WARNING: received an empty list, returning None.")
        return None

    stacked    = np.array(img_list, dtype=np.float32)
    mean_array = np.mean(stacked, axis=0)
    return np.round(mean_array).astype(np.uint8)


# ==============================================================================
# SECTION 6 — NODE DETECTION
# ==============================================================================
# These functions look at the binary mask produced by the ESPI pipeline and
# decide whether nodal regions are present.
#
# A NODE in a vibrating plate is a point or line that does NOT move.
# In an ESPI image, nodes appear as dark regions surrounded by bright fringes.
#
# Both functions are STUBS — not yet implemented.  Identical to camera_control.py.
# ==============================================================================

def detect_nodes(diff: np.ndarray, treshold_method: str = "otsu") -> np.ndarray:
    """
    Apply thresholding to a difference image to isolate node regions.

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

    Regions smaller than min_area pixels are ignored as noise.

    Args:
        binary   : binary image from detect_nodes() (uint8 numpy array)
        min_area : minimum region size in pixels to count as a real node

    NOTE: This function is not yet implemented.
    """
    # TODO: implement connected-component area check
    pass


# ==============================================================================
# SECTION 7 — FILE LOGGING
# ==============================================================================
# Identical to camera_control.py — these functions only deal with files and
# numpy arrays, so no camera-specific changes are needed.
# ==============================================================================

def build_filename(frequency_hz: float, exposure_us: float, step: str,
                   extension: str = "png") -> str:
    """
    Build a sortable filename for one captured image.

    The format is:  <step>_<date>_<frequency>Hz_<exposure>us.<extension>

    Example:
        build_filename(440.0, 10000, "espi_sweep")
        # Returns: "espi_sweep_2026-06-15_00440.0Hz_010000us.png"
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    _cleaned = f"{round(frequency_hz, 6):.6f}".rstrip("0")
    _dec = len(_cleaned.split(".")[1]) if "." in _cleaned else 0
    _dec = max(1, _dec)
    _width = 5 + 1 + _dec
    freq_str = f"{frequency_hz:0{_width}.{_dec}f}"
    return f"{step}_{date_str}_{freq_str}Hz_{exposure_us:06.0f}us.{extension}"


def _resolve_output_dir(output_dir: str | None) -> str | None:
    """Return a safe output directory for image saves.

    Relative paths are resolved against the current working directory.
    Absolute paths are allowed when they are inside the user's home directory,
    the current working directory, or the OS's own temp directory (this last
    one is what lets pytest's tmp_path fixture — which always lives under
    tempfile.gettempdir(), e.g. /tmp on Linux or /private/var/.../T on macOS —
    pass this check; without it, every test that saves to a real temp
    directory would be rejected the same way a genuinely unsafe path like
    "/" or "C:\\Windows" should be).
    """
    if output_dir is None:
        return os.path.join(os.path.expanduser("~"), "Desktop")

    expanded = os.path.expanduser(output_dir)
    if not os.path.isabs(expanded):
        return os.path.abspath(expanded)

    # realpath (not abspath) matters here: on macOS, tempfile.gettempdir()
    # returns a path through /var, which is itself a symlink to /private/var,
    # while pytest's tmp_path fixture reports the already-resolved
    # /private/var/... form. abspath() does not follow symlinks, so comparing
    # un-resolved paths would make this check reject pytest's own tmp_path
    # even after adding temp_dir as an allowed root.
    abs_dir = os.path.realpath(expanded)
    home_dir = os.path.realpath(os.path.expanduser("~"))
    cwd_dir = os.path.realpath(os.getcwd())
    temp_dir = os.path.realpath(tempfile.gettempdir())

    try:
        under_home = os.path.commonpath([home_dir, abs_dir]) == home_dir
        under_cwd = os.path.commonpath([cwd_dir, abs_dir]) == cwd_dir
        under_temp = os.path.commonpath([temp_dir, abs_dir]) == temp_dir
    except ValueError:
        print(f"[save_image] Refusing to use output directory on a different drive: {abs_dir}")
        return None

    if not under_home and not under_cwd and not under_temp:
        print(f"[save_image] Refusing to create output directory outside home/current working directory: {abs_dir}")
        return None

    return abs_dir


def save_image(image: np.ndarray, output_dir: str = None, frequency_hz: float = 0.0,
               exposure_us: float = 0.0, step: str = "frame", bit_depth: str = "8bit") -> str | None:
    """
    Save a numpy array to disk, naming the file automatically with build_filename().

    The output folder is created if it doesn't exist.
    If output_dir is not given, the image is saved to the Desktop.

    Args:
        image        : the image to save (numpy array)
        output_dir   : folder to save into (created automatically if missing)
        frequency_hz : drive frequency for this frame (goes into the filename)
        exposure_us  : exposure value for this frame (goes into the filename)
        step         : short label for the experimental step (goes into the filename)
        bit_depth    : "8bit"  → saves a PNG  (values 0–255)
                       "16bit" → saves a TIFF (values 0–65535)

    Returns the full path of the saved file, or None if saving failed.

    Example:
        path = save_image(frame, "output/", 440.0, 10000, "espi_sweep")
    """
    try:
        output_dir = _resolve_output_dir(output_dir)
        if output_dir is None:
            return None

        extension = "tiff" if bit_depth == "16bit" else "png"
        filename  = build_filename(frequency_hz, exposure_us, step, extension)
        filepath  = os.path.join(output_dir, filename)

        os.makedirs(output_dir, exist_ok=True)

        if bit_depth == "16bit":
            success = cv2.imwrite(filepath, image.astype(np.uint16))
        else:
            success = cv2.imwrite(filepath, image)

        if success:
            print(f"[save_image] Saved: {filepath}")
            return filepath
        else:
            print(f"[save_image] cv2.imwrite failed for: {filepath}")
            return None

    except Exception as e:
        print(f"[save_image] Error saving to {output_dir}: {e}")
        return None


def save_session_log(session_info: dict, output_dir: str) -> None:
    """
    Write the camera settings to a human-readable text file.

    Creates a file named "session_log_<timestamp>.txt" inside output_dir.
    Pass the dictionary returned by get_camera_info() as session_info.

    Example:
        info = get_camera_info(camera)
        save_session_log(info, "output/")
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path  = os.path.join(output_dir, f"session_log_{timestamp}.txt")

    with open(log_path, "w") as f:
        f.write(f"Session log — {timestamp}\n")
        f.write("=" * 40 + "\n")
        for key, value in session_info.items():
            f.write(f"{key}: {value}\n")

    print(f"[save_session_log] Log saved: {log_path}")


def log_frame_metadata(frame_index: int, exposure_us: float,
                       mean_brightness: float, output_dir: str) -> None:
    """
    Append one row of per-frame data to a CSV file in output_dir.

    The CSV file is named "frame_metadata.csv".  On the first call it is
    created with a header row.  Every subsequent call appends a new row,
    so you can call this inside a frame-grabbing loop.

    Args:
        frame_index     : which frame this is (0, 1, 2, ...)
        exposure_us     : exposure value used for this frame
        mean_brightness : average pixel value of the frame (0.0 to 255.0)
        output_dir      : folder where frame_metadata.csv will be written

    Example:
        for i, frame in enumerate(frames):
            log_frame_metadata(i, -6, float(np.mean(frame)), "output/")
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path     = os.path.join(output_dir, "frame_metadata.csv")
    write_header = not os.path.exists(csv_path)

    with open(csv_path, "a") as f:
        if write_header:
            f.write("frame_index,timestamp,exposure_value,mean_brightness\n")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        f.write(f"{frame_index},{timestamp},{exposure_us:.1f},{mean_brightness:.2f}\n")


# ==============================================================================
# SECTION 8 — QUICK VIEW
# ==============================================================================
# Identical to camera_control.py.
# ==============================================================================

def save_and_display_img(image: np.ndarray, filename: str = None) -> str | None:
    """
    Convert an image to black and white, save it to the current folder,
    and display it in a new window.

    The window blocks until you press any key, then closes automatically.

    Args:
        image    : the image to process (numpy array, any shape)
        filename : optional filename (without extension is fine — .png is added).
                   If omitted, a timestamped name is generated automatically.

    Returns the full path of the saved file, or None if saving failed.

    Example:
        save_and_display_img(frame)
        save_and_display_img(frame, "my_image")
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"image_{timestamp}.png"
    elif not filename.lower().endswith(".png"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"{filename}_{timestamp}.png"

    filepath = os.path.join(os.getcwd(), filename)

    success = cv2.imwrite(filepath, gray)
    if not success:
        print(f"[save_and_display_img] Failed to save: {filepath}")
        return None
    print(f"[save_and_display_img] Saved: {filepath}")

    cv2.imshow("Image", gray)
    cv2.waitKey(0)
    cv2.destroyWindow("Image")

    return filepath


# ==============================================================================
# SECTION 9 — LIVE FEED & CAPTURE
# ==============================================================================
# Two convenience functions that wrap the full two-phase workflow:
#
#   show_live_camera()    — opens a real-time window so you can aim and focus
#                           the camera before committing to a capture.
#                           Uses cv2.imshow (not matplotlib) because it refreshes
#                           fast enough for smooth video.  Press 'e' to exit.
#
#   capture_and_display() — takes n_images still photos, saves each one to the
#                           current folder, and displays each with matplotlib.
#                           Matplotlib is used here (not cv2.imshow) because it
#                           gives you a zoom/pan toolbar and pixel value readout.
#
# Typical usage:
#
#   show_live_camera(0)           # Phase 1: aim — press 'e' when ready
#   capture_and_display(0, 5)     # Phase 2: take 5 photos, save and display
# ==============================================================================

def show_live_camera(camera_index=0):
    """
    Open a real-time camera window so you can aim and check framing.

    The feed runs until you press 'e', then the window closes.
    This function manages its own camera connection — it opens the camera,
    runs the feed, and releases the camera when you press 'e'.

    cv2.imshow is used here instead of matplotlib because it can refresh
    fast enough for smooth video — matplotlib redraws too slowly for live feed.
    The bitwise AND with 0xFF in the key check is needed on some systems
    to read the key code correctly.

    Args:
        camera_index : integer (0 = first camera, 1 = second, etc.) or a
                       video file path string (e.g. 'clip.mp4').
                       Defaults to 0.

    Example:
        show_live_camera()            # first camera
        show_live_camera(1)           # second camera
        show_live_camera('clip.mp4')  # video file, useful for testing
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Could not open camera source: {camera_index}")
        return

    print("Live feed running — aim the camera, then press 'e' to exit.")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Failed to grab frame from live feed.")
            break

        cv2.imshow('Live Camera Feed', frame)

        # waitKey(1) waits 1 ms per loop — fast enough to show smooth video.
        if cv2.waitKey(1) & 0xFF == ord('e'):
            break

    cap.release()
    cv2.destroyAllWindows()


def show_live_feed_from_camera(camera):
    """
    Show a live camera feed using a camera handle you already have open.

    This is different from show_live_camera() in one important way:
    show_live_camera() opens its own camera connection from scratch, which
    means TWO connections to the same camera are briefly open at the same time.
    On some operating systems that causes a conflict and the feed fails.

    This function avoids the problem by reusing the camera handle you already
    created with connect_camera() — only one connection is ever open.

    An instruction overlay is drawn on the screen so you always know how to
    close the window.  Press 'e' when the plate is centred and in focus.

    Args:
        camera : the camera object returned by connect_camera()

    Example:
        camera = connect_camera()
        show_live_feed_from_camera(camera)   # aim, press 'e', then continue
        set_exposure_manual(camera, -6)      # now lock settings for measurement
    """
    print("Live feed open — aim the camera at the plate, then press 'e' to begin.")

    while True:
        ok, frame = camera.read()

        if not ok or frame is None:
            print("Live feed: failed to read a frame — stopping feed.")
            break

        # Draw "Press 'e' to start" in the top-left corner of the preview.
        # We work on a copy so the raw frame data is never modified.
        display = frame.copy()
        cv2.putText(
            display,
            "Press 'e' when ready to start",
            (10, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),   # bright green — visible against most backgrounds
            2,
            cv2.LINE_AA,
        )
        cv2.imshow("ESPI — Live Camera Feed", display)

        # waitKey(1) keeps the loop fast enough to show smooth video.
        if cv2.waitKey(1) & 0xFF == ord('e'):
            break

    cv2.destroyWindow("ESPI — Live Camera Feed")
    print("Live feed closed.")


def capture_and_display(camera_index=0, n_images=5, exposure=-6):
    """
    Take n_images still photos, save each one, and display each with matplotlib.

    This function manages its own camera connection — it opens the camera,
    captures the photos, and releases the camera when done.

    Each photo is:
      - converted to greyscale (black and white)
      - saved as a PNG in the current folder with a timestamp in the filename
        so photos from different sessions never overwrite each other
      - displayed in a matplotlib window (close the window to move to the next)

    Matplotlib is used for display (not cv2.imshow) because it provides an
    interactive toolbar — you can zoom, pan, and read individual pixel values
    by hovering over the image.

    OpenCV's exposure value is a log₂ scale in seconds:
        exposure time = 2^(exposure) seconds
        -1  ≈ 0.5 s  (bright),  -6 ≈ 15 ms (medium),  -11 ≈ 0.5 ms (dark)
    Not all cameras let OpenCV control exposure — if brightness does not
    change when you adjust this, your camera driver is ignoring it.

    Args:
        camera_index : integer camera index (0 = first, 1 = second, etc.).
                       Defaults to 0.
        n_images     : how many photos to take.  Defaults to 5.
        exposure     : OpenCV log₂ exposure value.  Defaults to -6 (≈ 15 ms).

    Returns:
        list : full file paths of every photo that was saved successfully.

    Example:
        paths = capture_and_display(0, 5, -6)
        print(paths)   # ['capture_1_2026-06-16_...png', ...]
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Could not open camera {camera_index}.")
        return []

    # Switch to manual exposure so brightness stays the same across all photos.
    # Value 1 = manual mode on most camera drivers.
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

    print(f"Taking {n_images} photo(s) from camera {camera_index}...\n")

    saved_files = []

    for i in range(n_images):
        ok, frame = cap.read()

        if not ok or frame is None:
            print(f"  [WARNING] Could not grab photo {i + 1}. Skipping.")
            continue

        # OpenCV delivers BGR even from a mono camera — convert to greyscale
        # so the saved array is a clean 2-D grid matching camera_control.py.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Timestamp in the filename prevents files from different sessions
        # overwriting each other.
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"capture_{i + 1}_{timestamp}.png"
        filepath  = os.path.join(os.getcwd(), filename)

        success = cv2.imwrite(filepath, gray)
        if not success:
            print(f"  [WARNING] Could not save photo {i + 1}.")
            continue

        print(f"  Photo {i + 1} saved: {filepath}")
        saved_files.append(filepath)

        # plt.show() blocks until the window is closed, then the loop moves on.
        print(f"  Showing photo {i + 1} — close the window to continue.")
        plt.imshow(gray, cmap='gray', interpolation='bicubic')
        plt.xticks([]), plt.yticks([])
        plt.title(f"Photo {i + 1} of {n_images}")
        plt.show()

    cap.release()
    print(f"\nDone. {len(saved_files)} photo(s) saved.")
    return saved_files


# ==============================================================================
# __all__ — WHAT GETS EXPORTED WITH "from camera_control_inclusive import *"
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
    "grab_single_frame_with_retry",
    "grab_n_frames",
    "grab_reference_frame",
    "discard_warmup_frames",

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

    # Section 8: Quick View
    "save_and_display_img",

    # Section 9: Live Feed & Capture
    "show_live_camera",
    "show_live_feed_from_camera",
    "capture_and_display",
]
