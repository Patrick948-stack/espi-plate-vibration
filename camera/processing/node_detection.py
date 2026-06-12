import numpy as np
import cv2

def detect_nodes(diff: np.ndarray, treshold_method: str= "otsu")->np.ndarray:
   """
    Apply thresholding to a difference image to isolate node regions.

    Args:
        diff: amplified difference image (uint8 grayscale)
        threshold_method: "otsu" or "manual"
    
    Returns binary image: 255 = node region, 0 = background
    """

def has_nodes(binary: np.ndarray, min_area: int = 100) -> bool:
    """
    Return True if the binary image contains node-like regions above a minimum area.
    Helps filter out noise.
    """
