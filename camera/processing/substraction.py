import numpy as np
import cv2


def substract_frames(previous: np.ndarray, current: np.ndarray) -> np.ndarray:
    """
    Compute absolute pixel-wise difference between two consecutive frames.
    Returns a uint8 grayscale difference image.
    """
    assert previous.shape == current.shape, (
        f"Frame shapes must match: {previous.shape} vs {current.shape}"
    )
    # cv2.absdiff clips at 0 instead of wrapping — safe for uint8.
    # Naive numpy subtraction (a - b) overflows silently: e.g. 10 - 20 = 246.
    return cv2.absdiff(previous, current)


def amplify_difference(diff: np.ndarray) -> np.ndarray:
    """
    Normalize the difference image to the full 0-255 range for visibility.
    Returns a uint8 image where the darkest pixel → 0 and brightest → 255.
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


def binarize_diff(diff: np.ndarray, method: str = "otsu") -> tuple[np.ndarray, float]:
    """
    Threshold the difference image to produce a binary mask.

    Args:
        diff:   grayscale difference image (uint8)
        method: "otsu" for automatic threshold, "manual" uses a fixed value of 127

    Returns:
        (binary_image, threshold_value)
        binary_image: uint8 array — 255 = changed region, 0 = background
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
    Display the raw diff, amplified diff, and optionally the binary mask
    in OpenCV windows. Press any key to close.
    """
    cv2.imshow("Difference (raw)", diff)
    cv2.imshow("Difference (amplified)", amplified)
    if binary is not None:
        cv2.imshow("Binary Mask", binary)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def run_espi_pipeline(reference: np.ndarray, live: np.ndarray) -> dict:
    """
    Run the full ESPI pipeline on a reference and live frame.

    Returns a dict with keys:
        'diff'      — raw absolute difference (uint8)
        'amplified' — contrast-stretched difference (uint8)
        'binary'    — Otsu-thresholded mask (uint8)
        'colored'   — false-colour amplified image for saving/display (uint8 BGR)
        'threshold' — Otsu threshold value used
    """
    diff = substract_frames(reference, live)
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
    Save a difference image to disk as a PNG.
    Returns True on success, False on failure.
    """
    success = cv2.imwrite(path, diff)
    if success:
        print(f"[save_diff] Saved to: {path}")
    else:
        print(f"[save_diff] Failed to save to: {path}")
    return success