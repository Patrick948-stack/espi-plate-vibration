from connection import connect_camera, disconnect_camera
from settings import set_exposure_manual, set_pixel_format, get_camera_info
from capture import grab_reference_frame, grab_n_frames
from roi import set_capture_roi, reset_capture_roi
from processing.substraction import run_espi_pipeline, show_diff
from processing.node_detection import detect_nodes, has_nodes
from utils.file_logger import build_filename, save_image


def test_connection():
    """Connect to the camera, print its settings, then disconnect."""
    cam = connect_camera()
    if cam is None:
        return
    print(get_camera_info(cam))
    disconnect_camera(cam)


def test_exposure():
    """Connect, apply a manual 5 ms exposure, confirm settings, disconnect."""
    cam = connect_camera()
    if cam is None:
        return
    set_exposure_manual(cam, 5000)
    print(get_camera_info(cam))
    disconnect_camera(cam)


def test_pixel_format():
    """Connect and set pixel format to Mono8 (default for ESPI work)."""
    cam = connect_camera()
    if cam is None:
        return
    set_pixel_format(cam, "Mono8")
    print(get_camera_info(cam))
    disconnect_camera(cam)


def test_roi():
    """Set a centre ROI, print info, then restore the full sensor."""
    cam = connect_camera()
    if cam is None:
        return
    set_capture_roi(cam, x=256, y=256, width=512, height=512)
    print(get_camera_info(cam))
    reset_capture_roi(cam)
    disconnect_camera(cam)


def test_subtraction():
    """Grab a reference frame and a live frame, run the ESPI pipeline, save result."""
    cam = connect_camera()
    if cam is None:
        return
    set_exposure_manual(cam, 10000)
    ref = grab_reference_frame(cam)
    # Grab one live frame to compare against the reference.
    live_frames = grab_n_frames(cam, 1)
    if ref is None or not live_frames:
        print("Could not acquire frames.")
        disconnect_camera(cam)
        return
    live = live_frames[0]
    result = run_espi_pipeline(ref, live)
    filename = build_filename("test", "espi_output", 1)
    save_image(result["colored"], filename)
    show_diff(result["diff"], result["amplified"], result["binary"])
    disconnect_camera(cam)


def test_logger():
    """Verify filename generation."""
    filename = build_filename("viola", "bracing_added", 1)
    print(filename)


if __name__ == "__main__":
    test_connection()
    # Uncomment each test as you complete and verify each module:
    # test_exposure()
    # test_pixel_format()
    # test_roi()
    # test_subtraction()
    # test_logger()
