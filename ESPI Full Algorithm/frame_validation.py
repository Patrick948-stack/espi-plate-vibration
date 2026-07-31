"""
frame_validation.py
===================
Defensive checks for camera frames.

Implements validation patterns from debug_camera_format.py to ensure:
- Frames have correct shape (H, W) or (H, W, 3)
- Frames have correct dtype (uint8)
- Color layout is correct (BGR vs RGB)
- Camera supports requested conversion methods

Used by monitor_gui.py to validate frames at the boundary after grabbing.
"""

import numpy as np


def validate_frame_format(frame, expected_shape_type="color"):
    """
    Validate frame shape and dtype before processing.

    Args:
        frame : numpy array from camera
        expected_shape_type : "color" for (H, W, 3), "grayscale" for (H, W),
                              "flexible" for either

    Raises:
        ValueError if shape is invalid
        TypeError if dtype is not uint8
    """
    if frame is None:
        raise ValueError("Frame is None")

    # Check dtype
    if frame.dtype != np.uint8:
        raise TypeError(f"Expected dtype uint8, got {frame.dtype}")

    # Check shape
    if expected_shape_type == "color":
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Expected 3-channel color (H, W, 3), got shape {frame.shape}"
            )
    elif expected_shape_type == "grayscale":
        if len(frame.shape) != 2:
            raise ValueError(
                f"Expected 2-channel grayscale (H, W), got shape {frame.shape}"
            )
    elif expected_shape_type == "flexible":
        if len(frame.shape) == 2:
            # Grayscale OK
            pass
        elif len(frame.shape) == 3:
            if frame.shape[2] != 3:
                raise ValueError(
                    f"For 3D array, expected 3 channels, got {frame.shape[2]}. Shape: {frame.shape}"
                )
        else:
            raise ValueError(f"Unexpected shape: {frame.shape}. Expected (H, W) or (H, W, 3)")


def validate_camera_supports_color(format_info, method):
    """
    Raise if single-channel extraction requested but camera is monochrome.

    Args:
        format_info : dict from connect_camera() containing "supports_color"
        method : grayscale conversion method ("standard" or "single_channel")

    Raises:
        ValueError if single_channel requested for mono camera
    """
    if method == "single_channel" and not format_info.get("supports_color", False):
        raise ValueError(
            f"Camera ({format_info.get('camera_type', 'unknown')}) is monochrome "
            f"but single-channel extraction requested. Use 'standard' method instead."
        )


def apply_format_correction(frame, format_info):
    """
    Apply channel swap if RGB→BGR mismatch detected.

    Args:
        frame : numpy array (H, W, 3) BGR or RGB
        format_info : dict from connect_camera() containing "needs_channel_swap"

    Returns:
        frame with corrected channel order
    """
    if frame is None:
        return None

    if format_info.get("needs_channel_swap", False):
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = frame[:, :, ::-1]  # Reverse channels: RGB → BGR

    return frame


def log_frame_info(frame, label="Frame"):
    """
    Log frame statistics for debugging.

    Args:
        frame : numpy array
        label : str description of the frame
    """
    if frame is None:
        print(f"  {label}: None")
        return

    print(f"  {label}:")
    print(f"    shape={frame.shape}, dtype={frame.dtype}")
    if len(frame.shape) >= 2:
        print(f"    min={np.min(frame)}, max={np.max(frame)}, mean={np.mean(frame):.1f}")
