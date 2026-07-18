"""
conftest.py — shared pytest fixtures for ESPI camera and signal generator tests.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Neutralize cv2's on-screen window functions for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_cv2_gui(monkeypatch):
    """
    Replace cv2.imshow / cv2.waitKey / cv2.destroyAllWindows with harmless
    fakes for every test, automatically.

    The real versions need a GUI backend (GTK on Linux, Cocoa on macOS) to
    even exist. CI installs opencv-python-headless, which has no GUI
    backend at all, so calling any of them raises
    cv2.error: "The function is not implemented." A test that forgets to
    fake one of these three (as several here did) passes locally, where a
    GUI-capable OpenCV is installed, and only fails once it reaches CI.

    A test that wants to check what was shown or which key was "pressed"
    can still patch these itself inside its own `with patch(...)` block;
    that inner patch simply overrides this one for its own scope.
    """
    monkeypatch.setattr("cv2.imshow", MagicMock())
    monkeypatch.setattr("cv2.waitKey", MagicMock(return_value=-1))
    monkeypatch.setattr("cv2.destroyAllWindows", MagicMock())


# ---------------------------------------------------------------------------
# Shared image fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gray_100x100():
    """A 100×100 uint8 greyscale image with varied pixel values."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(100, 100), dtype=np.uint8)


@pytest.fixture
def gray_100x100_b():
    """A second 100×100 uint8 greyscale image, slightly different from gray_100x100."""
    rng = np.random.default_rng(1)
    return rng.integers(0, 256, size=(100, 100), dtype=np.uint8)


@pytest.fixture
def uniform_gray():
    """A 50×50 image where every pixel has value 128."""
    return np.full((50, 50), 128, dtype=np.uint8)


@pytest.fixture
def black_image():
    """A 50×50 all-zero image."""
    return np.zeros((50, 50), dtype=np.uint8)


@pytest.fixture
def white_image():
    """A 50×50 all-255 image."""
    return np.full((50, 50), 255, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Mock OpenCV VideoCapture
# ---------------------------------------------------------------------------

def make_mock_cv2_camera(width=640, height=480, read_ok=True, frame=None):
    """
    Return a mock cv2.VideoCapture that looks like an open camera.

    Args:
        width, height : reported frame dimensions
        read_ok       : whether camera.read() should succeed
        frame         : the BGR numpy array camera.read() returns (auto-created if None)
    """
    if frame is None:
        frame = np.zeros((height, width, 3), dtype=np.uint8)

    mock = MagicMock()
    mock.isOpened.return_value = True
    mock.read.return_value = (read_ok, frame if read_ok else None)

    def _get(prop):
        mapping = {
            3: float(width),   # CAP_PROP_FRAME_WIDTH
            4: float(height),  # CAP_PROP_FRAME_HEIGHT
            5: 30.0,           # CAP_PROP_FPS
            15: -6.0,          # CAP_PROP_EXPOSURE
            14: 0.0,           # CAP_PROP_GAIN
            10: 128.0,         # CAP_PROP_BRIGHTNESS
        }
        return mapping.get(int(prop), 0.0)

    mock.get.side_effect = _get
    mock.set.return_value = True
    return mock


@pytest.fixture
def mock_cv2_camera():
    return make_mock_cv2_camera()


# ---------------------------------------------------------------------------
# Mock Basler (pypylon) camera
# ---------------------------------------------------------------------------

def make_mock_basler_camera(width=1920, height=1200):
    """Return a MagicMock that looks like a Basler InstantCamera."""
    cam = MagicMock()
    cam.GetDeviceInfo().GetModelName.return_value = "MockBasler"
    cam.GetDeviceInfo().GetSerialNumber.return_value = "MOCK_SN"

    # Width / Height props
    cam.Width.Value = width
    cam.Width.Max   = width
    cam.Width.Min   = 4
    cam.Width.Inc   = 4

    cam.Height.Value = height
    cam.Height.Max   = height
    cam.Height.Min   = 4
    cam.Height.Inc   = 4

    # Offsets
    cam.OffsetX.Value = 0
    cam.OffsetX.Inc   = 4
    cam.OffsetY.Value = 0
    cam.OffsetY.Inc   = 4

    # Exposure
    cam.ExposureTime.Min   = 10.0
    cam.ExposureTime.Max   = 100_000.0
    cam.ExposureTime.Value = 10_000.0

    # Gain
    cam.Gain.Min   = 0.0
    cam.Gain.Max   = 24.0
    cam.Gain.Value = 0.0

    # Pixel format
    cam.PixelFormat.Value = "Mono8"

    # Grabbing control
    cam.IsGrabbing.return_value = False

    return cam


@pytest.fixture
def mock_basler_camera():
    return make_mock_basler_camera()


# ---------------------------------------------------------------------------
# Mock pyvisa instrument
# ---------------------------------------------------------------------------

def make_mock_instrument(identity="SDG,SDG1015,MOCK,1.0"):
    """Return a MagicMock that looks like an open pyvisa resource."""
    instr = MagicMock()
    instr.query.side_effect = lambda cmd: {
        '*IDN?':       identity,
        'C1:OUTP?':    'C1:OUTP ON,LOAD,HZ,PLRT,NOR',
        'C2:OUTP?':    'C2:OUTP OFF,LOAD,HZ,PLRT,NOR',
        'C1:BSWV?':    'C1:BSWV WVTP,SINE,FRQ,1000HZ,AMP,1V,OFST,0V',
        'C2:BSWV?':    'C2:BSWV WVTP,SINE,FRQ,1000HZ,AMP,1V,OFST,0V',
    }.get(cmd.strip(), 'UNKNOWN')
    instr.write.return_value = None
    return instr


@pytest.fixture
def mock_instrument():
    return make_mock_instrument()
