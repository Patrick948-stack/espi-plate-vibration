"""
Test suite for single-channel grayscale conversion algorithms and UI in monitor_gui.py

Tests cover:
1. Grayscale conversion algorithm backends (Pillow, NumPy, OpenCV)
2. SettingsPage UI state management for grayscale method selection
3. Frame format conversions between numpy/PIL/QImage
4. Edge cases and error handling
"""

import numpy as np
import pytest
from PIL import Image
from unittest.mock import Mock, MagicMock

import cv2
import sys
sys.path.insert(0, '/Users/patrickmulikuza/Desktop/My projects/Physics Research/ESPI Full Algorithm')

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Import the module we're testing
import monitor_gui


class TestGrayscaleConversionAlgorithms:
    """Test single-channel grayscale conversion algorithm implementations."""

    @pytest.fixture
    def sample_bgr_frame(self):
        """Create a mock BGR frame (OpenCV format)."""
        # Create a 10x10 BGR frame with distinct values per channel
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame[:, :, 0] = 100  # Blue channel
        frame[:, :, 1] = 150  # Green channel
        frame[:, :, 2] = 200  # Red channel
        return frame

    @pytest.fixture
    def sample_rgb_frame(self):
        """Create a mock RGB frame (PIL format)."""
        # Create a 10x10 RGB frame
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame[:, :, 0] = 200  # Red channel
        frame[:, :, 1] = 150  # Green channel
        frame[:, :, 2] = 100  # Blue channel
        return frame

    def test_pillow_red_channel_extraction(self, sample_rgb_frame):
        """Test extracting red channel using Pillow."""
        pil_img = Image.fromarray(sample_rgb_frame, mode='RGB')

        # Extract red channel
        red_channel = np.array(pil_img.getchannel('R'))

        # Verify the red channel values
        assert red_channel.dtype == np.uint8
        assert np.all(red_channel == 200)
        assert red_channel.shape == (10, 10)

    def test_pillow_green_channel_extraction(self, sample_rgb_frame):
        """Test extracting green channel using Pillow."""
        pil_img = Image.fromarray(sample_rgb_frame, mode='RGB')

        green_channel = np.array(pil_img.getchannel('G'))

        assert green_channel.dtype == np.uint8
        assert np.all(green_channel == 150)

    def test_pillow_blue_channel_extraction(self, sample_rgb_frame):
        """Test extracting blue channel using Pillow."""
        pil_img = Image.fromarray(sample_rgb_frame, mode='RGB')

        blue_channel = np.array(pil_img.getchannel('B'))

        assert blue_channel.dtype == np.uint8
        assert np.all(blue_channel == 100)

    def test_numpy_slicing_red_channel(self, sample_bgr_frame):
        """Test extracting red channel using NumPy slicing (BGR layout)."""
        # In OpenCV BGR, Red is at index 2
        red_channel = sample_bgr_frame[:, :, 2]

        assert red_channel.dtype == np.uint8
        assert np.all(red_channel == 200)
        assert red_channel.shape == (10, 10)

    def test_numpy_slicing_green_channel(self, sample_bgr_frame):
        """Test extracting green channel using NumPy slicing (BGR layout)."""
        # In OpenCV BGR, Green is at index 1
        green_channel = sample_bgr_frame[:, :, 1]

        assert green_channel.dtype == np.uint8
        assert np.all(green_channel == 150)

    def test_numpy_slicing_blue_channel(self, sample_bgr_frame):
        """Test extracting blue channel using NumPy slicing (BGR layout)."""
        # In OpenCV BGR, Blue is at index 0
        blue_channel = sample_bgr_frame[:, :, 0]

        assert blue_channel.dtype == np.uint8
        assert np.all(blue_channel == 100)

    def test_opencv_hsv_masking_red(self, sample_bgr_frame):
        """Test red color extraction using HSV masking."""
        hsv = cv2.cvtColor(sample_bgr_frame, cv2.COLOR_BGR2HSV)

        # Red hue ranges (wraps around at 0 and 180)
        mask1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
        color_mask = cv2.bitwise_or(mask1, mask2)

        # For a pure red image, we should get a mask with non-zero values
        assert color_mask.shape == (10, 10)
        assert color_mask.dtype == np.uint8

    def test_opencv_hsv_masking_green(self, sample_bgr_frame):
        """Test green color extraction using HSV masking."""
        hsv = cv2.cvtColor(sample_bgr_frame, cv2.COLOR_BGR2HSV)

        # Green hue range
        color_mask = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([85, 255, 255]))

        assert color_mask.shape == (10, 10)
        assert color_mask.dtype == np.uint8

    def test_opencv_hsv_masking_blue(self, sample_bgr_frame):
        """Test blue color extraction using HSV masking."""
        hsv = cv2.cvtColor(sample_bgr_frame, cv2.COLOR_BGR2HSV)

        # Blue hue range
        color_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([140, 255, 255]))

        assert color_mask.shape == (10, 10)
        assert color_mask.dtype == np.uint8

    def test_numpy_output_is_uint8(self, sample_bgr_frame):
        """Verify that grayscale conversion output is uint8."""
        red_channel = sample_bgr_frame[:, :, 2]

        assert red_channel.dtype == np.uint8
        assert red_channel.min() >= 0
        assert red_channel.max() <= 255

    def test_pillow_rgb_to_grayscale_merge(self, sample_rgb_frame):
        """Test Pillow approach of extracting and merging channels."""
        pil_img = Image.fromarray(sample_rgb_frame, mode='RGB')

        # Extract and replicate red channel
        red_channel = pil_img.getchannel('R')
        grayscale_img = Image.merge('RGB', (red_channel, red_channel, red_channel))

        # Convert to array and verify all channels are equal
        result = np.array(grayscale_img)
        assert result.shape == (10, 10, 3)
        assert np.all(result[:, :, 0] == result[:, :, 1])
        assert np.all(result[:, :, 1] == result[:, :, 2])


class TestSettingsPageGrayscaleUI:
    """Test SettingsPage UI controls for grayscale method selection."""

    @pytest.fixture(scope="session")
    def qapp(self):
        """Create QApplication for entire test session."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    @pytest.fixture
    def settings_page(self, qapp):
        """Create a SettingsPage instance for testing."""
        # Mock setup page to avoid extra dependencies
        mock_setup = Mock()
        page = monitor_gui.SettingsPage(mock_setup)
        # Show the page so that isVisible() returns True for child widgets
        page.show()
        return page

    def test_settings_page_has_grayscale_method_group(self, settings_page):
        """Test that SettingsPage has a grayscale method selection group."""
        assert hasattr(settings_page, '_grayscale_radios')
        assert "standard" in settings_page._grayscale_radios
        assert "single_channel" in settings_page._grayscale_radios

    def test_settings_page_has_color_channel_options(self, settings_page):
        """Test that SettingsPage has color channel selection options."""
        assert hasattr(settings_page, '_color_combo')
        assert settings_page._color_combo.count() == 3  # Red, Green, Blue

    def test_settings_page_has_algorithm_backend_options(self, settings_page):
        """Test that SettingsPage has algorithm backend options."""
        assert hasattr(settings_page, '_backend_combo')
        assert settings_page._backend_combo.count() == 3  # NumPy, Pillow, OpenCV HSV

    def test_default_grayscale_method_is_single_channel(self, settings_page):
        """Test default grayscale method is Single-Channel."""
        assert settings_page.grayscale_method() == "single_channel"

    def test_default_color_is_red(self, settings_page):
        """Test default color channel is Red."""
        assert settings_page.grayscale_color() == "R"

    def test_default_backend_is_numpy(self, settings_page):
        """Test default backend algorithm is NumPy."""
        assert settings_page.grayscale_backend() == "numpy"

    def test_visibility_updates_correctly(self, settings_page):
        """Test that _update_grayscale_ui_visibility correctly toggles visibility."""
        # Set to single-channel and update visibility
        settings_page._grayscale_radios["single_channel"].setChecked(True)
        settings_page._update_grayscale_ui_visibility()
        assert settings_page._color_combo.isVisible()
        assert settings_page._backend_combo.isVisible()
        assert settings_page._color_label.isVisible()
        assert settings_page._backend_label.isVisible()

        # Set to standard and update visibility
        settings_page._grayscale_radios["standard"].setChecked(True)
        settings_page._update_grayscale_ui_visibility()
        assert not settings_page._color_combo.isVisible()
        assert not settings_page._backend_combo.isVisible()
        assert not settings_page._color_label.isVisible()
        assert not settings_page._backend_label.isVisible()

    def test_color_selection_returns_correct_letter(self, settings_page):
        """Test that grayscale_color() returns R, G, or B."""
        settings_page._color_combo.setCurrentIndex(0)
        assert settings_page.grayscale_color() == "R"

        settings_page._color_combo.setCurrentIndex(1)
        assert settings_page.grayscale_color() == "G"

        settings_page._color_combo.setCurrentIndex(2)
        assert settings_page.grayscale_color() == "B"

    def test_backend_selection_returns_correct_value(self, settings_page):
        """Test that grayscale_backend() returns the correct backend name."""
        settings_page._backend_combo.setCurrentIndex(0)
        assert settings_page.grayscale_backend() == "numpy"

        settings_page._backend_combo.setCurrentIndex(1)
        assert settings_page.grayscale_backend() == "pillow"

        settings_page._backend_combo.setCurrentIndex(2)
        assert settings_page.grayscale_backend() == "opencv_hsv"


class TestFrameFormatConversions:
    """Test frame format conversions between different representations."""

    @pytest.fixture
    def sample_grayscale_frame(self):
        """Create a sample grayscale frame."""
        frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        return frame

    @pytest.fixture
    def sample_bgr_frame(self):
        """Create a sample BGR frame."""
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        return frame

    def test_grayscale_frame_to_qpixmap(self, sample_grayscale_frame):
        """Test converting grayscale numpy array to QPixmap."""
        pixmap = monitor_gui._frame_to_pixmap(sample_grayscale_frame)

        assert pixmap is not None
        assert not pixmap.isNull()
        assert pixmap.width() == 640
        assert pixmap.height() == 480

    def test_frame_to_pixmap_preserves_dtype(self, sample_grayscale_frame):
        """Test that frame_to_pixmap handles uint8 frames correctly."""
        # Ensure the frame is uint8 and contiguous
        frame = np.ascontiguousarray(sample_grayscale_frame, dtype=np.uint8)

        pixmap = monitor_gui._frame_to_pixmap(frame)
        assert not pixmap.isNull()

    def test_frame_to_pixmap_with_non_contiguous_array(self):
        """Test that frame_to_pixmap handles non-contiguous arrays."""
        frame = np.zeros((480, 640), dtype=np.uint8)
        # Make it non-contiguous by transposing then transposing back
        frame = np.asfortranarray(frame)

        # Should not raise error
        pixmap = monitor_gui._frame_to_pixmap(frame)
        assert not pixmap.isNull()

    def test_bgr_to_grayscale_conversion(self, sample_bgr_frame):
        """Test converting BGR frame to grayscale."""
        # Using OpenCV's conversion
        gray = cv2.cvtColor(sample_bgr_frame, cv2.COLOR_BGR2GRAY)

        assert gray.shape == (480, 640)
        assert gray.dtype == np.uint8

    def test_pillow_image_to_bgr_frame(self):
        """Test converting PIL Image to BGR numpy frame."""
        # Create a PIL Image
        pil_img = Image.new('RGB', (640, 480), color=(100, 150, 200))

        # Convert to numpy array
        bgr_frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        assert bgr_frame.shape == (480, 640, 3)
        assert bgr_frame.dtype == np.uint8


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_empty_frame_handling(self):
        """Test handling of empty frames."""
        empty_frame = np.array([], dtype=np.uint8)

        # Should not crash, even with empty input
        # Implementation will define behavior
        pass

    def test_single_pixel_frame(self):
        """Test handling of single-pixel frames."""
        frame = np.array([[128]], dtype=np.uint8)

        pixmap = monitor_gui._frame_to_pixmap(frame)
        assert not pixmap.isNull()

    def test_very_large_frame(self):
        """Test handling of very large frames."""
        frame = np.zeros((4096, 4096), dtype=np.uint8)

        pixmap = monitor_gui._frame_to_pixmap(frame)
        assert not pixmap.isNull()
        assert pixmap.width() == 4096
        assert pixmap.height() == 4096

    def test_invalid_color_selection(self):
        """Test handling of invalid color selections."""
        # This test will be implemented after UI is added
        pass

    def test_invalid_algorithm_backend(self):
        """Test handling of invalid algorithm backend selection."""
        # This test will be implemented after UI is added
        pass


class TestAlgorithmIntegration:
    """Integration tests for complete grayscale conversion pipeline."""

    @pytest.fixture
    def sample_bgr_frame(self):
        """Create a realistic sample BGR frame."""
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        return frame

    def test_numpy_algorithm_end_to_end(self, sample_bgr_frame):
        """Test complete NumPy algorithm: BGR -> channel extraction -> grayscale."""
        # Extract red channel
        red_grayscale = sample_bgr_frame[:, :, 2]

        # Verify output
        assert red_grayscale.dtype == np.uint8
        assert red_grayscale.shape == (480, 640)
        assert 0 <= red_grayscale.min() <= 255
        assert 0 <= red_grayscale.max() <= 255

    def test_pillow_algorithm_end_to_end(self):
        """Test complete Pillow algorithm: RGB Image -> channel extraction -> merge."""
        # Create a random RGB image
        rgb_frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        pil_img = Image.fromarray(rgb_frame, mode='RGB')

        # Extract red channel
        red_channel = pil_img.getchannel('R')

        # Merge to create grayscale
        grayscale_img = Image.merge('RGB', (red_channel, red_channel, red_channel))

        # Convert to numpy
        result = np.array(grayscale_img)

        assert result.shape == (480, 640, 3)
        assert result.dtype == np.uint8
        # All channels should be identical
        assert np.all(result[:, :, 0] == result[:, :, 1])

    def test_opencv_algorithm_end_to_end(self):
        """Test complete OpenCV HSV algorithm: BGR -> HSV conversion -> masking."""
        bgr_frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)

        # Convert to HSV
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)

        # Create red color mask
        mask1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
        color_mask = cv2.bitwise_or(mask1, mask2)

        # Convert to grayscale for comparison
        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Apply mask
        output = np.where(color_mask[:, :, None] == 255, gray_3ch, bgr_frame)

        assert output.shape == bgr_frame.shape
        assert output.dtype == np.uint8


class TestApplyGrayscaleConversionDispatcher:
    """Test the _apply_grayscale_conversion dispatcher function."""

    @pytest.fixture
    def sample_bgr_frame(self):
        """Create a sample BGR frame."""
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame[:, :, 0] = 100  # Blue
        frame[:, :, 1] = 150  # Green
        frame[:, :, 2] = 200  # Red
        return frame

    def test_standard_grayscale_conversion(self, sample_bgr_frame):
        """Test standard full-RGB grayscale conversion."""
        result = monitor_gui._apply_grayscale_conversion(
            sample_bgr_frame, method="standard"
        )

        assert result.shape == (10, 10)
        assert result.dtype == np.uint8

    def test_single_channel_numpy_backend(self, sample_bgr_frame):
        """Test single-channel conversion with NumPy backend."""
        result = monitor_gui._apply_grayscale_conversion(
            sample_bgr_frame, method="single_channel", color="R", backend="numpy"
        )

        assert result.shape == (10, 10)
        assert result.dtype == np.uint8
        assert np.all(result == 200)  # Red channel value

    def test_single_channel_pillow_backend(self, sample_bgr_frame):
        """Test single-channel conversion with Pillow backend."""
        result = monitor_gui._apply_grayscale_conversion(
            sample_bgr_frame, method="single_channel", color="G", backend="pillow"
        )

        assert result.shape == (10, 10)
        assert result.dtype == np.uint8

    def test_single_channel_opencv_hsv_backend(self, sample_bgr_frame):
        """Test single-channel conversion with OpenCV HSV backend."""
        result = monitor_gui._apply_grayscale_conversion(
            sample_bgr_frame, method="single_channel", color="B", backend="opencv_hsv"
        )

        assert result.shape == (10, 10)
        assert result.dtype == np.uint8

    def test_invalid_method_raises_error(self, sample_bgr_frame):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError, match="Invalid method"):
            monitor_gui._apply_grayscale_conversion(
                sample_bgr_frame, method="invalid_method"
            )

    def test_invalid_backend_raises_error(self, sample_bgr_frame):
        """Test that invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="Invalid backend"):
            monitor_gui._apply_grayscale_conversion(
                sample_bgr_frame, method="single_channel", backend="invalid_backend"
            )

    def test_grayscale_frame_passthrough(self):
        """Test that grayscale (2D) frames are returned as-is."""
        # Create a 2D grayscale frame (as returned by Mono8 cameras)
        grayscale_frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)

        # Apply standard conversion (should just return as-is)
        result = monitor_gui._apply_grayscale_conversion(
            grayscale_frame, method="standard"
        )

        assert result.shape == (480, 640)
        assert np.array_equal(result, grayscale_frame)

    def test_grayscale_frame_with_single_channel_ignored(self):
        """Test that single_channel method is ignored for 2D frames."""
        grayscale_frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)

        # Even with single_channel selected, 2D frame should be returned as-is
        result = monitor_gui._apply_grayscale_conversion(
            grayscale_frame, method="single_channel", color="R", backend="numpy"
        )

        assert result.shape == (480, 640)
        assert np.array_equal(result, grayscale_frame)

    def test_single_channel_3d_frame_reshaped_to_2d(self):
        """Test that 3D single-channel frames (H, W, 1) are reshaped to 2D."""
        # Some cameras return (H, W, 1) instead of (H, W) for grayscale
        single_channel_3d_frame = np.random.randint(0, 256, (480, 640, 1), dtype=np.uint8)

        result = monitor_gui._apply_grayscale_conversion(
            single_channel_3d_frame, method="standard"
        )

        # Should be reshaped to 2D
        assert result.shape == (480, 640)
        assert result.dtype == np.uint8
        # Values should match the original channel
        assert np.array_equal(result, single_channel_3d_frame.squeeze())
