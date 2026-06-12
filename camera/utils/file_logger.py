import cv2
import numpy as np
import os
from datetime import datetime


def build_filename(instrument: str, step: str, frame_index: int, extension: str = "png") -> str:
    """
    Build a consistent filename for a captured image.
    Example: viola_bracing_added_2026-06-08_003.png
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Zero-pad frame index to 3 digits so files sort correctly in the filesystem.
    return f"{instrument}_{step}_{date_str}_{frame_index:03d}.{extension}"


def save_image(image: np.ndarray, filepath: str, bit_depth: str = "8bit") -> bool:
    """
    Save an image to disk. Handles both 8-bit PNG and 16-bit TIFF.
    Returns True if successful.
    """
    try:
        # Create the parent directory if it doesn't exist yet.
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        if bit_depth == "16bit":
            # Convert to uint16 before writing — required for 16-bit TIFF.
            # Camera arrays may arrive as uint8 or uint16; astype() handles both.
            img_16 = image.astype(np.uint16)
            success = cv2.imwrite(filepath, img_16)
        else:
            # Standard 8-bit PNG — no conversion needed for uint8 arrays.
            success = cv2.imwrite(filepath, image)

        if success:
            print(f"[save_image] Saved: {filepath}")
        else:
            print(f"[save_image] cv2.imwrite failed for: {filepath}")
        return success

    except Exception as e:
        print(f"[save_image] Error saving {filepath}: {e}")
        return False


def save_session_log(session_info: dict, output_dir: str) -> None:
    """
    Save a text log of the session settings (exposure, pixel format, ROI, etc.)
    so results are reproducible.
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
    Append one row of per-frame metadata to a CSV in output_dir.
    Creates the file with a header on first call; appends on subsequent calls.
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

