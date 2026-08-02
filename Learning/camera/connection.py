from pypylon import pylon
from pypylon import genicam

def connect_camera():
    """
    Find the first available Basler camera. Return None if no camera is found. Return the InstantCamera object if found.
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
    Close the camera connection.
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