import numpy as np
from pypylon import pylon, genicam


def grab_single_frame(camera):
    """
    Grab one frame and return it as a numpy array.
    Return None if grab failed.
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
    Grab n frames and return them as a list of numpy arrays.
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
    Grab a single frame intended to be used as the ESPI reference.
    """
    # Reuses grab_single_frame — a reference is just a captured frame that the
    # ESPI pipeline treats as the zero-displacement baseline.
    frame = grab_single_frame(camera)
    if frame is not None:
        print(f"Reference frame captured — shape: {frame.shape}, dtype: {frame.dtype}")
    return frame