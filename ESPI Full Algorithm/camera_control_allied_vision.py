"""
camera_control_allied_vision.py
================================
Camera library for Allied Vision cameras using the VimbaPy (Vimba X) SDK.

Author: Patrick Mulikuza

This file has the same function names and the same arguments as
camera_control.py (Basler) and camera_control_inclusive.py (OpenCV).
To switch pipelines, change only the import line in your script:

    from camera_control import *                 <- Basler only
    from camera_control_inclusive import *       <- any OpenCV camera
    from camera_control_allied_vision import *   <- Allied Vision cameras

Everything else in your pipeline stays the same.

HARDWARE SUPPORTED
------------------
Any Allied Vision camera that works with the Vimba SDK:
    USB3 Vision cameras (e.g. Mako, Manta, Alvium USB)
    GigE Vision cameras (e.g. Manta, Prosilica)

INSTALL THE SDK FIRST
---------------------
1. Install the Vimba X SDK from Allied Vision's website.
2. Install the Python wrapper (vmbpy is NOT on PyPI):
       pip install git+https://github.com/alliedvision/VmbPy.git
   or download the wheel from the releases page and run:
       pip install vmbpy-x.x.x-py3-none-any.whl

EXPOSURE UNITS
--------------
Allied Vision cameras accept exposure in MICROSECONDS.
Pass 10000 for 10 ms, 100000 for 100 ms, etc.

HOW THIS FILE IS ORGANISED
---------------------------
  Section 1 — Camera Connection     : open and close the link to the camera
  Section 2 — Camera Settings       : exposure, gain, pixel format, info
  Section 3 — Region of Interest    : hardware ROI (faster than software crop)
  Section 4 — Image Capture         : grab frames as numpy arrays
  Section 5 — ESPI Image Processing : subtract, amplify, threshold, average
  Section 6 — Node Detection        : stubs, not yet implemented
  Section 7 — File Logging          : save images and session data to disk
  Section 8 — Quick View            : save and display a single image
  Section 9 — Live Feed and Capture : live camera window and multi-photo capture

DEPENDENCIES
------------
    pip install numpy opencv-python matplotlib
    + vmbpy from https://github.com/alliedvision/VmbPy
"""

# Python 3.10 introduced "str | None" as a shorthand for Optional[str].
# This line makes Python treat all type annotations as strings at runtime,
# so the same syntax works on Python 3.9 and earlier without crashing.
from __future__ import annotations

import cv2
import numpy as np
import os
import traceback
from datetime import datetime
from matplotlib import pyplot as plt

# ---------------------------------------------------------------------------
# Try to import vmbpy. If it is not installed, set a flag and print a clear
# message rather than crashing immediately — this lets the rest of the file
# load so unrelated functions (image processing, file saving) still work.
# ---------------------------------------------------------------------------
try:
    from vmbpy import VmbSystem as Vimba, FrameStatus, VmbFeatureError as VimbaFeatureError
    _VIMBA_AVAILABLE = True
except ImportError:
    _VIMBA_AVAILABLE = False
    print("[camera_control_allied_vision] WARNING: vmbpy package not found.")
    print("  Download from: https://github.com/alliedvision/VmbPy")
    print("  Then run: pip install <downloaded_wheel>.whl")


# ==============================================================================
# INTERNAL CAMERA HANDLE
# ==============================================================================
# VimbaPy uses Python context managers (the `with` keyword) to keep the SDK
# and camera alive.  Normally you would write:
#
#     with Vimba.get_instance() as vimba:
#         with vimba.get_all_cameras()[0] as cam:
#             frame = cam.get_frame()
#
# But our pipeline needs to open the camera once and share it across many
# function calls.  To do that we call __enter__ and __exit__ manually and
# store the open handles in this small wrapper class.
#
# connect_camera() creates and returns one of these.
# disconnect_camera() calls __exit__ on both handles to close everything.
# Every other function in this file takes a camera handle as its first arg.
# ==============================================================================

class _AVHandle:
    """
    Keeps the Vimba SDK and one open camera alive between function calls.

    Do not create this directly. Use connect_camera() and disconnect_camera().
    """
    def __init__(self, vimba_instance, camera):
        self._vimba = vimba_instance
        self._cam   = camera

    @property
    def cam(self):
        """The raw vmbpy Camera object, used when calling SDK methods directly."""
        return self._cam


# ==============================================================================
# INTERNAL ROI STORE
# ==============================================================================
# Software crop fallback: if hardware ROI fails we store the desired rectangle
# here and apply it manually after every frame grab.
_roi_store = {}


# ==============================================================================
# SECTION 1 — CAMERA CONNECTION
# ==============================================================================

def connect_camera(camera_index: int = 0) -> _AVHandle | None:
    """
    Open an Allied Vision camera by index and return a handle.

    camera_index = 0 means the first camera the SDK detects.
    If you have more than one plugged in, try 1, 2, etc.

    Returns an _AVHandle on success, or None if the camera could not be found.

    Example:
        camera = connect_camera()
        if camera is None:
            print("No camera found — check the cable.")
    """
    if not _VIMBA_AVAILABLE:
        print("[connect_camera] Cannot connect: vmbpy is not installed.")
        return None

    try:
        vimba = Vimba.get_instance()
        vimba.__enter__()          # start the Vimba SDK

        cameras = vimba.get_all_cameras()
        if not cameras:
            print("[connect_camera] No Allied Vision cameras detected.")
            print("  Check the USB or GigE cable and Vimba SDK installation.")
            vimba.__exit__(None, None, None)
            return None

        if camera_index >= len(cameras):
            print(f"[connect_camera] Camera index {camera_index} is out of range "
                  f"— only {len(cameras)} camera(s) detected.")
            vimba.__exit__(None, None, None)
            return None

        cam = cameras[camera_index]
        cam.__enter__()            # open the specific camera

        model  = cam.get_name()
        width  = cam.Width.get()
        height = cam.Height.get()
        print(f"Connected to Allied Vision: {model}  ({width} x {height} px)")

        return _AVHandle(vimba, cam)

    except Exception as e:
        print(f"[connect_camera] Failed to connect: {e}")
        traceback.print_exc()
        return None


def disconnect_camera(camera: _AVHandle) -> None:
    """
    Close the camera and release the Vimba SDK.

    Always call this when you are done — even if an error happened earlier.
    Not calling it can leave the SDK in a locked state that prevents the next run
    from connecting.

    Example:
        disconnect_camera(camera)
    """
    # Remove any stored ROI for this camera handle.
    _roi_store.pop(id(camera), None)

    try:
        camera.cam.__exit__(None, None, None)
        camera._vimba.__exit__(None, None, None)
        print("Allied Vision camera disconnected.")
    except Exception as e:
        print(f"[disconnect_camera] Error during disconnect: {e}")


# ==============================================================================
# SECTION 2 — CAMERA SETTINGS
# ==============================================================================

def set_exposure_manual(camera: _AVHandle, exposure_us: float) -> float | None:
    """
    Turn off auto-exposure and lock the camera to an exact exposure time.

    Exposure is in MICROSECONDS: 10000 = 10 ms, 100000 = 100 ms.
    If the requested value is outside the camera's hardware range, it is
    automatically clamped and a warning is printed.

    Returns the actual exposure the camera applied, or None on failure.

    Example:
        actual = set_exposure_manual(camera, 10000)   # request 10 ms
    """
    try:
        cam = camera.cam

        # Disable auto-exposure so the camera stops adjusting brightness.
        # Some camera models do not have this feature, so the error is ignored.
        try:
            cam.ExposureAuto.set('Off')
        except VimbaFeatureError:
            pass

        # Read the camera's hardware limits and clamp our request to them.
        min_exp, max_exp = cam.ExposureTime.get_range()
        clamped = max(min_exp, min(exposure_us, max_exp))

        if clamped != exposure_us:
            print(f"[set_exposure_manual] Requested {exposure_us} µs is outside "
                  f"the hardware range [{min_exp:.0f}, {max_exp:.0f}] µs. "
                  f"Using {clamped:.0f} µs instead.")

        cam.ExposureTime.set(clamped)
        actual = cam.ExposureTime.get()
        print(f"  Exposure locked: {actual:.1f} µs  (requested {exposure_us} µs)")
        return actual

    except Exception as e:
        print(f"[set_exposure_manual] Error: {e}")
        return None


def set_exposure_auto(camera: _AVHandle) -> None:
    """
    Let the camera adjust exposure automatically.

    Do NOT use this during a measurement sweep. If brightness changes between
    frames the subtraction result will be meaningless.

    Example:
        set_exposure_auto(camera)
    """
    try:
        camera.cam.ExposureAuto.set('Continuous')
        print("  Exposure set to automatic.")
    except VimbaFeatureError:
        print("[set_exposure_auto] Auto-exposure not supported on this camera.")


def set_gain_manual(camera: _AVHandle, gain: float) -> float | None:
    """
    Lock the camera to a specific gain value in dB.

    0.0 dB means no amplification. Higher values brighten a dark image but
    also amplify noise, which degrades the ESPI fringe pattern.
    Keep gain at 0.0 unless the plate is too dark even at maximum exposure.

    Returns the actual gain the camera applied, or None on failure.

    Example:
        set_gain_manual(camera, 0.0)
    """
    try:
        cam = camera.cam

        try:
            cam.GainAuto.set('Off')
        except VimbaFeatureError:
            pass

        min_gain, max_gain = cam.Gain.get_range()
        clamped = max(min_gain, min(gain, max_gain))

        if clamped != gain:
            print(f"[set_gain_manual] Requested gain {gain} dB is outside "
                  f"[{min_gain:.2f}, {max_gain:.2f}] dB. "
                  f"Using {clamped:.2f} dB instead.")

        cam.Gain.set(clamped)
        actual = cam.Gain.get()
        print(f"  Gain locked: {actual:.2f} dB  (requested {gain} dB)")
        return actual

    except Exception as e:
        print(f"[set_gain_manual] Error: {e}")
        return None


def set_gain_auto(camera: _AVHandle) -> None:
    """
    Let the camera adjust gain automatically.

    Example:
        set_gain_auto(camera)
    """
    try:
        camera.cam.GainAuto.set('Continuous')
        print("  Gain set to automatic.")
    except VimbaFeatureError:
        print("[set_gain_auto] Auto-gain not supported on this camera.")


def set_pixel_format(camera: _AVHandle, pixel_format: str = "Mono8") -> None:
    """
    Set the pixel format the camera uses to deliver frames.

    'Mono8' is recommended for ESPI: 8-bit greyscale (0-255), smallest files,
    no conversion needed. 'Mono12' gives more dynamic range if the plate
    contrast is too low in 8-bit, but requires normalisation before display.

    Example:
        set_pixel_format(camera, "Mono8")
    """
    try:
        camera.cam.set_pixel_format(pixel_format)
        print(f"  Pixel format set to: {pixel_format}")
    except Exception as e:
        print(f"[set_pixel_format] Could not set format '{pixel_format}': {e}")


def get_camera_info(camera: _AVHandle) -> dict:
    """
    Read the current camera settings and return them as a dictionary.

    Keys: model, width, height, fps, exposure, gain, pixel_format.
    Values that cannot be read are set to None.

    Example:
        info = get_camera_info(camera)
        print(info['model'], info['exposure'])
    """
    cam = camera.cam
    try:
        info = {
            "model":        cam.get_name(),
            "width":        cam.Width.get(),
            "height":       cam.Height.get(),
            "fps":          cam.AcquisitionFrameRate.get() if _feature_exists(cam, "AcquisitionFrameRate") else None,
            "exposure":     cam.ExposureTime.get(),
            "gain":         cam.Gain.get(),
            "pixel_format": str(cam.get_pixel_format()),
        }
    except Exception as e:
        print(f"[get_camera_info] Could not read all features: {e}")
        info = {}
    return info


def _feature_exists(cam, feature_name: str) -> bool:
    """Return True if this camera model supports the named SDK feature."""
    try:
        cam.get_feature_by_name(feature_name)
        return True
    except Exception:
        return False


# ==============================================================================
# SECTION 3 — REGION OF INTEREST (ROI)
# ==============================================================================
# Allied Vision cameras support HARDWARE ROI: the sensor physically reads
# only the rectangle you specify, so fewer pixels travel over the USB/GigE
# cable and the frame rate increases.
# This is a real speed advantage over camera_control_inclusive.py, which can
# only crop in software after the full frame has already arrived.
# ==============================================================================

def set_capture_roi(camera: _AVHandle, x: int, y: int,
                    width: int, height: int) -> None:
    """
    Tell the sensor to read only a rectangular sub-area (hardware ROI).

    All values are automatically clamped to the sensor's physical limits.

    Args:
        camera : the handle from connect_camera()
        x      : left edge in pixels, measured from the left of the sensor
        y      : top edge in pixels, measured from the top of the sensor
        width  : width of the ROI in pixels
        height : height of the ROI in pixels

    Example:
        set_capture_roi(camera, x=256, y=256, width=512, height=512)
    """
    try:
        cam = camera.cam
        max_w = cam.WidthMax.get()
        max_h = cam.HeightMax.get()

        x      = max(0, min(x, max_w - 1))
        y      = max(0, min(y, max_h - 1))
        width  = max(1, min(width,  max_w - x))
        height = max(1, min(height, max_h - y))

        # Width and Height must be set before OffsetX/Y — this is a Vimba SDK rule.
        cam.Width.set(width)
        cam.Height.set(height)
        cam.OffsetX.set(x)
        cam.OffsetY.set(y)

        _roi_store[id(camera)] = (x, y, width, height)
        print(f"[set_capture_roi] Hardware ROI: x={x}, y={y}, "
              f"width={width}, height={height}")

    except Exception as e:
        print(f"[set_capture_roi] Hardware ROI failed: {e}. Falling back to software crop.")
        _roi_store[id(camera)] = (x, y, width, height)


def reset_capture_roi(camera: _AVHandle) -> None:
    """
    Remove the ROI and go back to reading the full sensor.

    Example:
        reset_capture_roi(camera)
    """
    _roi_store.pop(id(camera), None)

    try:
        cam = camera.cam
        max_w = cam.WidthMax.get()
        max_h = cam.HeightMax.get()

        # Offsets must be reset to 0 before restoring full Width/Height.
        cam.OffsetX.set(0)
        cam.OffsetY.set(0)
        cam.Width.set(max_w)
        cam.Height.set(max_h)
        print(f"[reset_capture_roi] Full sensor restored ({max_w} x {max_h} px).")
    except Exception as e:
        print(f"[reset_capture_roi] Error restoring full sensor: {e}")


def _apply_roi(frame: np.ndarray, camera) -> np.ndarray:
    """
    Internal helper — applies a software crop if hardware ROI was not available.
    Returns the frame unchanged if no ROI is stored for this camera handle.
    """
    roi = _roi_store.get(id(camera))
    if roi is None:
        return frame
    x, y, w, h = roi
    return frame[y: y + h, x: x + w]


# ==============================================================================
# SECTION 4 — IMAGE CAPTURE
# ==============================================================================

def _to_gray(img: np.ndarray) -> np.ndarray:
    """
    Internal helper — convert any camera output to a 2D greyscale array.

    Allied Vision mono cameras (model suffix 'm') return shape (H, W, 1):
    three dimensions but only one channel. Colour cameras return (H, W, 3).
    A plain greyscale array has shape (H, W) with no channel dimension at all.

    Checking only ndim == 3 is not enough to know if an image is colour,
    because (H, W, 1) also has 3 dimensions. We must check shape[2] too.
    """
    if img.ndim == 3:
        if img.shape[2] == 1:
            # Mono camera wraps the greyscale data in a redundant third dimension.
            # [:, :, 0] means: all rows, all columns, first (and only) channel.
            return img[:, :, 0]
        # Colour camera — convert BGR (OpenCV's channel order) to greyscale.
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Already a flat 2D greyscale array.
    return img


def grab_single_frame(camera: _AVHandle,
                      timeout_ms: int = 2000) -> np.ndarray | None:
    """
    Grab exactly one frame and return it as a 2D uint8 numpy array.

    Args:
        camera     : the handle from connect_camera()
        timeout_ms : how long to wait for a frame before giving up (milliseconds).
                     Default is 2000 ms (2 seconds). Increase if the camera is
                     on a slow GigE network.

    Returns a (height x width) uint8 array, or None if the grab failed.

    Example:
        frame = grab_single_frame(camera)
        if frame is not None:
            print(frame.shape)   # e.g. (1944, 2592)
    """
    try:
        frame = camera.cam.get_frame(timeout_ms=timeout_ms)

        if frame.get_status() != FrameStatus.Complete:
            print(f"[grab_single_frame] Incomplete frame — status: {frame.get_status()}")
            return None

        img = frame.as_numpy_ndarray()
        img = _to_gray(img)

        # Normalise to uint8 if the camera is in a 12-bit or 16-bit mode.
        # ESPI processing assumes 8-bit (0-255), so we rescale here.
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        return _apply_roi(img, camera)

    except Exception as e:
        print(f"[grab_single_frame] Error: {e}")
        return None


def grab_single_frame_with_retry(camera: _AVHandle,
                                  max_retries: int = 3) -> np.ndarray | None:
    """
    Like grab_single_frame(), but retries on failure.

    GigE cameras can drop an occasional packet. Retrying a couple of times
    handles this without aborting the whole sweep.

    Returns a numpy array on success, or None if all attempts failed.

    Example:
        frame = grab_single_frame_with_retry(camera, max_retries=3)
    """
    for attempt in range(max_retries):
        frame = grab_single_frame(camera)
        if frame is not None:
            return frame
        if attempt < max_retries - 1:
            print(f"  Frame grab failed — retrying ({attempt + 2}/{max_retries})...")

    print(f"[grab_single_frame_with_retry] All {max_retries} attempt(s) failed.")
    return None


def grab_n_frames(camera: _AVHandle, n: int,
                  max_retries: int = 3) -> list:
    """
    Grab n frames in a row and return them as a list of numpy arrays.

    The returned list may be shorter than n if some frames fail even after
    retrying — callers should check len(result) before using it.

    Example:
        frames = grab_n_frames(camera, 2)
        if len(frames) < 2:
            print("Not enough frames.")
    """
    frames = []
    for _ in range(n):
        frame = grab_single_frame_with_retry(camera, max_retries=max_retries)
        if frame is not None:
            frames.append(frame)
    return frames


def grab_reference_frame(camera: _AVHandle) -> np.ndarray | None:
    """
    Grab one frame to use as the ESPI baseline reference.

    Call this BEFORE turning on the signal generator so the plate is at rest.
    Every measurement frame in reference-subtraction mode is compared to this.

    Example:
        ref = grab_reference_frame(camera)
    """
    frame = grab_single_frame(camera)
    if frame is not None:
        print(f"Reference frame captured — shape: {frame.shape}, dtype: {frame.dtype}")
    return frame


def discard_warmup_frames(camera: _AVHandle, n: int = 5) -> None:
    """
    Grab and throw away the first n frames so the sensor can settle.

    Call this after opening the camera or after changing exposure or gain.
    The first few frames often still reflect the previous setting and will
    corrupt the ESPI result if used in a subtraction.

    Example:
        set_exposure_manual(camera, 10000)
        discard_warmup_frames(camera, n=5)
    """
    print(f"  Discarding {n} warmup frame(s) to let the sensor settle...")
    discarded = sum(
        1 for _ in range(n)
        if grab_single_frame(camera) is not None
    )
    print(f"  Done — {discarded}/{n} warmup frames cleared.")


# ==============================================================================
# SECTION 5 — ESPI IMAGE PROCESSING
# ==============================================================================
# These functions only work on numpy arrays — they have no camera dependency.
# They are identical across all three camera_control_*.py files.
# ==============================================================================

def substract_frames(previous: np.ndarray,
                     current: np.ndarray) -> np.ndarray | None:
    """
    Compute the absolute pixel-wise difference between two frames.

    cv2.absdiff is used instead of plain numpy subtraction because numpy
    wraps uint8 values: 10 - 20 = 246 (wrong). absdiff gives abs(10-20) = 10.

    Returns a uint8 numpy array, or None if the shapes do not match.

    Example:
        diff = substract_frames(frame_a, frame_b)
    """
    if previous.shape != current.shape:
        print(f"[substract_frames] Shape mismatch: "
              f"{previous.shape} vs {current.shape}.")
        return None
    return cv2.absdiff(previous, current)


def amplify_difference(diff: np.ndarray) -> np.ndarray:
    """
    Stretch contrast so the darkest pixel becomes 0 and the brightest becomes 255.

    Raw ESPI difference images are usually very dark — the plate barely moves
    so the pixel changes are tiny. This makes the fringe pattern visible.

    Example:
        amplified = amplify_difference(diff)
    """
    return cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)


def binarize_diff(diff: np.ndarray, method: str = "otsu") -> tuple:
    """
    Threshold the difference image to produce a black-and-white mask.

    'otsu' automatically finds the best threshold based on the image histogram.
    'manual' uses a fixed threshold of 127.

    Returns (binary_image, threshold_value).

    Example:
        binary, threshold = binarize_diff(amplified)
    """
    if method == "otsu":
        thresh_val, binary = cv2.threshold(
            diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        thresh_val, binary = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)

    print(f"[binarize_diff] Threshold used: {thresh_val}")
    return binary, thresh_val


def show_diff(diff: np.ndarray, amplified: np.ndarray,
              binary: np.ndarray = None) -> None:
    """
    Display raw difference, amplified, and optional binary images. Press any key to close.

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

    Returns a dictionary with keys:
        'diff', 'amplified', 'binary', 'colored', 'threshold'

    Example:
        result = run_espi_pipeline(frame_a, frame_b)
        save_image(result["amplified"], "output/", 440.0, 10000, "test")
    """
    diff      = substract_frames(reference, live)
    amplified = amplify_difference(diff)
    binary, threshold = binarize_diff(amplified, method="otsu")
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
    Save a difference image to disk as a PNG.

    Returns True on success, False on failure.

    Example:
        save_diff(result["amplified"], "output/amplified_001.png")
    """
    success = cv2.imwrite(path, diff)
    if success:
        print(f"[save_diff] Saved: {path}")
    else:
        print(f"[save_diff] Failed to save: {path}")
    return success


def average_img(img_list: list) -> np.ndarray | None:
    """
    Compute the element-wise average of a list of images.

    Averaging multiple difference images reduces random noise. The more frames
    you average, the cleaner the fringe pattern, but the longer it takes.

    Returns a uint8 numpy array, or None if the list is empty.

    Example:
        averaged = average_img(difference_images)
    """
    if not img_list:
        print("[average_img] WARNING: empty list — nothing to average.")
        return None

    # Stack into a 3D array (n_images x H x W) using float32 so the mean
    # is not truncated to an integer during the calculation.
    stacked = np.array(img_list, dtype=np.float32)
    return np.round(np.mean(stacked, axis=0)).astype(np.uint8)


# ==============================================================================
# SECTION 6 — NODE DETECTION
# ==============================================================================

def detect_nodes(diff: np.ndarray, treshold_method: str = "otsu") -> np.ndarray:
    """
    Isolate node regions in a difference image.

    NOTE: Not yet implemented.
    """
    # TODO: implement node detection logic
    pass


def has_nodes(binary: np.ndarray, min_area: int = 100) -> bool:
    """
    Return True if the binary image contains any node-like regions.

    NOTE: Not yet implemented.
    """
    # TODO: implement connected-component area check
    pass


# ==============================================================================
# SECTION 7 — FILE LOGGING
# ==============================================================================

def build_filename(frequency_hz: float, exposure_us: float,
                   step: str, extension: str = "png") -> str:
    """
    Build a sortable filename for one captured image.

    Format: <step>_<date>_<frequency>Hz_<exposure>us.<extension>
    Zero-padded frequency and exposure so files sort correctly in the OS.

    Example:
        build_filename(440.0, 10000, "espi_raw")
        # -> "espi_raw_2026-06-22_00440.0Hz_010000us.png"
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    _cleaned = f"{round(frequency_hz, 6):.6f}".rstrip("0")
    _dec = len(_cleaned.split(".")[1]) if "." in _cleaned else 0
    _dec = max(1, _dec)
    _width = 5 + 1 + _dec
    freq_str = f"{frequency_hz:0{_width}.{_dec}f}"
    return (f"{step}_{date_str}_{freq_str}Hz_"
            f"{exposure_us:06.0f}us.{extension}")


def save_image(image: np.ndarray, output_dir: str = None,
               frequency_hz: float = 0.0, exposure_us: float = 0.0,
               step: str = "frame", bit_depth: str = "8bit") -> str | None:
    """
    Save a numpy array to disk with an auto-generated, sortable filename.

    Args:
        image        : the image to save (numpy array)
        output_dir   : folder to save into. Created automatically if it does
                       not exist. Defaults to the Desktop if None.
        frequency_hz : drive frequency for this frame, used in the filename.
        exposure_us  : camera exposure in µs, used in the filename.
        step         : short label for the experimental step, e.g. "espi_raw".
        bit_depth    : "8bit" saves as PNG. "16bit" saves as TIFF.

    Returns the full saved path as a string, or None on failure.

    Example:
        path = save_image(diff, "output/", 440.0, 10000, "espi_raw")
    """
    try:
        if output_dir is None:
            output_dir = os.path.join(os.path.expanduser("~"), "Desktop")

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
        print(f"[save_image] Error: {e}")
        return None


def save_session_log(session_info: dict, output_dir: str) -> None:
    """
    Write camera settings to a human-readable text file.

    Pass the dictionary returned by get_camera_info() as session_info.
    The file is named session_log_<timestamp>.txt and goes into output_dir.

    Example:
        save_session_log(get_camera_info(camera), "output/")
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
    Append one row to frame_metadata.csv in output_dir.

    On the first call the file is created with a header. Every subsequent
    call appends a row — call this inside a frame-grabbing loop.

    Example:
        for i, frame in enumerate(frames):
            log_frame_metadata(i, 10000, float(np.mean(frame)), "output/")
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path     = os.path.join(output_dir, "frame_metadata.csv")
    write_header = not os.path.exists(csv_path)

    with open(csv_path, "a") as f:
        if write_header:
            f.write("frame_index,timestamp,exposure_us,mean_brightness\n")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        f.write(f"{frame_index},{timestamp},{exposure_us:.1f},{mean_brightness:.2f}\n")


# ==============================================================================
# SECTION 8 — QUICK VIEW
# ==============================================================================

def save_and_display_img(image: np.ndarray,
                          filename: str = None) -> str | None:
    """
    Convert to greyscale, save to the current folder, and show in a window.

    The window blocks until you press any key, then closes automatically.

    Example:
        save_and_display_img(frame)
        save_and_display_img(frame, "my_image")
    """
    gray = _to_gray(image)

    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"image_{timestamp}.png"
    elif not filename.lower().endswith(".png"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"{filename}_{timestamp}.png"

    filepath = os.path.join(os.getcwd(), filename)
    if not cv2.imwrite(filepath, gray):
        print(f"[save_and_display_img] Failed to save: {filepath}")
        return None

    print(f"[save_and_display_img] Saved: {filepath}")
    cv2.imshow("Image", gray)
    cv2.waitKey(0)
    cv2.destroyWindow("Image")
    return filepath


# ==============================================================================
# SECTION 9 — LIVE FEED AND CAPTURE
# ==============================================================================

def show_live_feed_from_camera(camera: _AVHandle) -> None:
    """
    Show a live camera feed in a window until the user presses 'e'.

    Uses the vmbpy streaming API so frames arrive continuously in a background
    thread and the display stays smooth without the main loop having to poll.

    Press 'e' (or close the window) to stop the feed and return to the caller.

    Example:
        camera = connect_camera()
        show_live_feed_from_camera(camera)
        set_exposure_manual(camera, 10000)
    """
    print("Live feed open — aim the camera at the plate, then press 'e' to begin.")

    # Shared container for the latest frame.
    #
    # Why a list instead of a plain variable?
    # In Python 3, a nested function can READ a variable from the outer scope
    # but cannot REASSIGN it without the `nonlocal` keyword. Using a one-element
    # list is a common workaround: we modify the list's contents (latest[0] = x)
    # rather than the variable itself, which is allowed without nonlocal.
    latest = [None]

    def _handler(cam, stream, frame):
        # This function is called by the vmbpy SDK in a background thread
        # each time a new frame arrives from the camera.
        #
        # The three arguments are required by the vmbpy API:
        #   cam    : the Camera object that produced the frame
        #   stream : the Stream object (we do not use it here)
        #   frame  : the Frame object containing the pixel data
        #
        # IMPORTANT: after we are done with the frame we MUST call
        # cam.queue_frame(frame) to return it to the SDK's buffer pool.
        # If we forget, the SDK runs out of buffers and stops delivering frames.
        try:
            if frame.get_status() == FrameStatus.Complete:
                img = frame.as_numpy_ndarray()
                latest[0] = _to_gray(img)
        except Exception as e:
            print(f"[live feed] Frame handler error: {e}")
        finally:
            # Always re-queue the frame, even if processing raised an exception.
            cam.queue_frame(frame)

    try:
        # buffer_count controls how many frames the SDK pre-allocates in memory.
        # 5 is enough for a smooth preview — more would waste RAM.
        camera.cam.start_streaming(_handler, buffer_count=5)

        while True:
            if latest[0] is not None:
                display = latest[0].copy()
                cv2.putText(
                    display,
                    "Press 'e' to start the sweep",
                    (10, 34),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    255,       # white text — visible on a greyscale image
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("ESPI — Live Camera Feed", display)

            # waitKey(1) waits 1 ms for a key press and returns its ASCII code.
            # & 0xFF masks the result to 8 bits for compatibility across platforms.
            if cv2.waitKey(1) & 0xFF == ord('e'):
                break

    finally:
        # stop_streaming() and destroyWindow() must run even if an exception
        # is raised inside the while loop — that is why they are in `finally`.
        camera.cam.stop_streaming()
        cv2.destroyWindow("ESPI — Live Camera Feed")
        print("Live feed closed.")


def capture_and_display(camera: _AVHandle, n_images: int = 5) -> list:
    """
    Take n_images still photos, save each to the current folder, and display.

    Each photo is saved as a greyscale PNG with a timestamp in the filename,
    then shown in a matplotlib window. Close each window to continue.

    Args:
        camera   : the handle from connect_camera()
        n_images : how many photos to take. Defaults to 5.

    Returns a list of the saved file paths.

    Example:
        paths = capture_and_display(camera, 5)
    """
    print(f"Taking {n_images} photo(s)...")
    saved_files = []

    for i in range(n_images):
        frame = grab_single_frame_with_retry(camera)
        if frame is None:
            print(f"  [WARNING] Could not grab photo {i + 1} — skipping.")
            continue

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"capture_{i + 1}_{timestamp}.png"
        filepath  = os.path.join(os.getcwd(), filename)

        if not cv2.imwrite(filepath, frame):
            print(f"  [WARNING] Could not save photo {i + 1}.")
            continue

        print(f"  Photo {i + 1} saved: {filepath}")
        saved_files.append(filepath)

        print(f"  Showing photo {i + 1} — close the window to continue.")
        plt.imshow(frame, cmap='gray')
        plt.xticks([]), plt.yticks([])
        plt.title(f"Photo {i + 1} of {n_images}")
        plt.show()

    print(f"\nDone. {len(saved_files)}/{n_images} photo(s) saved.")
    return saved_files


# ==============================================================================
# __all__ — CONTROLS WHAT GETS EXPORTED WITH "from camera_control_allied_vision import *"
# ==============================================================================
# Only the public API is listed here. Internal helpers (_AVHandle, _roi_store,
# _feature_exists, _apply_roi, _to_gray) are not exported — they are
# implementation details that callers should not depend on.
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

    # Section 9: Live Feed
    "show_live_feed_from_camera",
    "capture_and_display",
]
