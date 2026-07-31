"""
Debug script to diagnose camera pixel format and grayscale conversion issues.

Uses Pylon ImageFormatConverter to properly capture native RGB8 frames,
then demonstrates grayscale conversion methods.

Shows a sequence of images:
1. Raw frame 1 (native RGB from camera)
2. Raw frame 2 (native RGB from camera)
3. Frame 1 (standard grayscale via cv2.cvtColor)
4. Frame 2 (standard grayscale via cv2.cvtColor)
5. Frame 1 (numpy slicing - R channel only)
6. Frame 2 (numpy slicing - R channel only)
7. Difference (frame1_std - frame2_std)
8. Difference (frame1_numpy - frame2_numpy)

Navigate with LEFT/RIGHT arrow keys to step through images.
Press 'Q' to quit.
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from pypylon import pylon

# Add ESPI Full Algorithm to path
project_root = Path(__file__).parent
espi_dir = project_root / "ESPI Full Algorithm"
sys.path.insert(0, str(espi_dir))

import camera_control


def display_image_sequence(images_with_labels):
    """
    Display a sequence of images, allowing navigation with arrow keys.

    Parameters:
        images_with_labels : list of (image_array, label_string) tuples
    """
    current_idx = 0
    window_name = "Camera Debug - Navigation: A/D or LEFT/RIGHT arrows, Q to quit"

    print("\n   Keyboard shortcuts:")
    print("   - A or LEFT arrow:  Previous image")
    print("   - D or RIGHT arrow: Next image")
    print("   - Q: Quit\n")

    while True:
        img = images_with_labels[current_idx][0]
        label = images_with_labels[current_idx][1]

        # Create a copy to draw text on
        display_img = img.copy()

        # Defensive check: ensure image format is valid before display
        if len(display_img.shape) == 2:  # Single-channel grayscale (H, W)
            display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2BGR)
        elif len(display_img.shape) == 3:
            if display_img.shape[2] != 3:
                raise ValueError(f"Image has {display_img.shape[2]} channels, expected 1 or 3 channels. Shape: {display_img.shape}")
            # Else: already 3-channel color, use as-is
        else:
            raise ValueError(f"Unexpected image shape: {display_img.shape}. Expected (H, W) or (H, W, 3)")

        # Add label at top
        cv2.putText(
        display_img,           # Image to draw on
        label,                 # Text to display
        (10, 30),              # (x, y) position in pixels — top-left corner is (0, 0)
        cv2.FONT_HERSHEY_SIMPLEX,  # Font style
        1.0,                   # Font scale (size: 1.0 = normal, 2.0 = 2x bigger, etc.)
        (0, 255, 0),           # Color in BGR: (Blue, Green, Red)
        2                      # Thickness in pixels (line width)
        )


        # Add navigation info at bottom
        nav_text = f"[{current_idx + 1}/{len(images_with_labels)}] A/D or arrows to navigate, Q to quit"
        cv2.putText(
            display_img,
            nav_text,
            (10, display_img.shape[0] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 0),
            1
        )

        cv2.imshow(window_name, display_img)

        key = cv2.waitKey(0)

        # Handle different key code formats (platform-dependent)
        # Lower 8 bits for printable characters, full 32 bits for special keys
        key_code = key & 0xFF
        key_full = key & 0xFFFFFF

        if key_code == ord('q') or key_code == ord('Q'):
            cv2.destroyAllWindows()
            break
        # A key or LEFT arrow (codes: 97 for 'a', 65 for 'A', 81 or 65361 for LEFT)
        elif key_code == ord('a') or key_code == ord('A') or key_full == 65361 or key == 81:
            current_idx = (current_idx - 1) % len(images_with_labels)
            print(f"← Previous image [{current_idx + 1}/{len(images_with_labels)}]")
        # D key or RIGHT arrow (codes: 100 for 'd', 68 for 'D', 83 or 65363 for RIGHT)
        elif key_code == ord('d') or key_code == ord('D') or key_full == 65363 or key == 83:
            current_idx = (current_idx + 1) % len(images_with_labels)
            print(f"→ Next image [{current_idx + 1}/{len(images_with_labels)}]")


def main():
    print("=" * 80)
    print("BASLER CAMERA DEBUG - DEFAULT FORMAT CAPTURE")
    print("=" * 80)

    camera = None
    try:
        # Step 1: Connect to camera
        print("\n1. Connecting to Basler camera...")
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()
        camera = pylon.InstantCamera(device)
        camera.Open()
        print(f"✓ Connected to: {camera.GetDeviceInfo().GetModelName()}")

        # Step 2: Read the camera's default format (DO NOT change it)
        print("\n2. Reading camera's default pixel format...")
        default_format = camera.PixelFormat.GetValue()
        print(f"   Camera default format: {default_format}")

        # Step 2b: Check for format mismatch upfront
        print("\n2b. Checking for format mismatch...")
        target_format = "BGR8packed"
        needs_channel_swap = False

        if default_format == "RGB8":
            needs_channel_swap = True
            print(f"   ⚠️  Format mismatch detected:")
            print(f"       Camera outputs: {default_format}")
            print(f"       Converter outputs: {target_format}")
            print(f"   ⚠️  Will apply R↔B channel swap during frame capture")
        elif default_format == "BGR8":
            print(f"   ✓ Format match: Camera is {default_format}, no swap needed")
        else:
            print(f"   ⚠️  Unknown format: {default_format} (may need manual testing)")

        # # COMMENTED OUT: Step 2b - Force specific format
        # print("\n2b. Setting camera to native RGB8 format...")
        # try:
        #     camera.PixelFormat.SetValue("RGB8")
        #     print(f"   Camera format: {camera.PixelFormat.Value}")
        #     print("   ✓ RGB8 set successfully")
        # except Exception as e:
        #     print(f"   ✗ RGB8 not supported: {e}")
        #     print("   Trying BayerRG8 fallback...")
        #     try:
        #         camera.PixelFormat.SetValue("BayerRG8")
        #         print(f"   Camera format: {camera.PixelFormat.Value}")
        #         print("   ✓ BayerRG8 set as fallback")
        #     except Exception as bayer_e:
        #         print(f"   ✗ BayerRG8 also failed: {bayer_e}")
        #         print("   This may be a monochrome camera.")
        #         camera.Close()
        #         return

        # Step 3: Configure Pylon converter to output BGR8 for OpenCV compatibility
        print("\n3. Configuring Pylon ImageFormatConverter for BGR8 output (OpenCV standard)...")
        converter = pylon.ImageFormatConverter()
        # Set to BGR8packed since OpenCV (cv2.imshow) expects BGR, not RGB
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        target_format = "BGR8packed"
        print(f"   ✓ Converter set to output {target_format}")

        # # COMMENTED OUT: Step 3b - Force RGB8 output
        # print("\n3b. Configuring Pylon ImageFormatConverter for RGB8 output...")
        # converter = pylon.ImageFormatConverter()
        # converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        # converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        # print("   ✓ Converter configured")

        # Step 4: Set exposure
        print("\n4. Setting exposure to 120ms...")
        camera.ExposureTime.SetValue(60000)  # 60000 microseconds = 60ms
        print("   ✓ Exposure set")

        # Step 5: Grab two frames using converter
        print("\n5. Grabbing two consecutive frames with native format...")
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        frame1 = None
        frame2 = None

        grabResult1 = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grabResult1.GrabSucceeded():
            converted1 = converter.Convert(grabResult1)
            frame1 = converted1.GetArray().copy()
            print(f"   ✓ Frame 1 captured: shape={frame1.shape}, dtype={frame1.dtype}")

            # Preemptive safety block: Apply channel swap if mismatch detected
            if needs_channel_swap:
                frame1 = frame1[:, :, ::-1]  # Swap R and B channels
        grabResult1.Release()

        grabResult2 = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grabResult2.GrabSucceeded():
            converted2 = converter.Convert(grabResult2)
            frame2 = converted2.GetArray().copy()
            print(f"   ✓ Frame 2 captured: shape={frame2.shape}, dtype={frame2.dtype}")

            # Preemptive safety block: Apply channel swap if mismatch detected
            if needs_channel_swap:
                frame2 = frame2[:, :, ::-1]  # Swap R and B channels
        grabResult2.Release()

        camera.StopGrabbing()

        if frame1 is None or frame2 is None:
            print("   ❌ Failed to grab frames")
            camera.Close()
            return

        # Debug: Check frame shape
        print(f"\n*** DEBUG: Frame 1 shape = {frame1.shape}")
        print(f"*** DEBUG: Frame 1 ndim = {frame1.ndim} (should be 2 for grayscale, 3 for RGB)")
        if frame1.ndim == 3:
            print(f"*** DEBUG: Frame has {frame1.shape[2]} channels")

        # Step 6: Verify frames are 3-channel color
        print("\n6. Verifying frame format...")
        if len(frame1.shape) != 3 or frame1.shape[2] != 3:
            print(f"   ✗ Expected (H, W, 3) BGR, got {frame1.shape}")
            camera.Close()
            return
        print(f"   ✓ Frames are proper 3-channel color: {frame1.shape}")

        # Step 7: Convert to grayscale using two methods
        print("\n7. Converting frames to grayscale...")

        # Method 1: cv2.cvtColor (standard - BGR to GRAY, since frames are now BGR)
        print("   - Method 1: cv2.cvtColor BGR→GRAY (standard)")
        frame1_std = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        frame2_std = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        print(f"     Frame 1 std: min={np.min(frame1_std)}, max={np.max(frame1_std)}, mean={np.mean(frame1_std):.1f}")
        print(f"     Frame 2 std: min={np.min(frame2_std)}, max={np.max(frame2_std)}, mean={np.mean(frame2_std):.1f}")

        # Method 2: NumPy slicing (Red channel only - R is at index 2 in BGR)
        print("   - Method 2: NumPy slicing (R channel at index 2 in BGR)")
        frame1_numpy = frame1[:, :, 2]  # R channel is at index 2 in BGR
        frame2_numpy = frame2[:, :, 2]
        print(f"     Frame 1 numpy: min={np.min(frame1_numpy)}, max={np.max(frame1_numpy)}, mean={np.mean(frame1_numpy):.1f}")
        print(f"     Frame 2 numpy: min={np.min(frame2_numpy)}, max={np.max(frame2_numpy)}, mean={np.mean(frame2_numpy):.1f}")

        # Step 8: Compute differences
        print("\n8. Computing frame differences...")
        diff_std = cv2.absdiff(frame1_std, frame2_std)
        diff_numpy = cv2.absdiff(frame1_numpy, frame2_numpy)

        print(f"   - Difference (standard): min={np.min(diff_std)}, max={np.max(diff_std)}, mean={np.mean(diff_std):.1f}")
        print(f"   - Difference (numpy):    min={np.min(diff_numpy)}, max={np.max(diff_numpy)}, mean={np.mean(diff_numpy):.1f}")

        # Step 9: Prepare image sequence for display
        print("\n9. Preparing image sequence for display...")
        images = [
            (frame1, "1. Raw Frame 1 (Corrected BGR - RED laser)"),
            (frame2, "2. Raw Frame 2 (Corrected BGR - RED laser)"),
            (frame1_std, "3. Frame 1 - Standard Grayscale (cv2.cvtColor BGR→GRAY)"),
            (frame2_std, "4. Frame 2 - Standard Grayscale (cv2.cvtColor BGR→GRAY)"),
            (frame1_numpy, "5. Frame 1 - Red Channel Only (BGR index 2)"),
            (frame2_numpy, "6. Frame 2 - Red Channel Only (BGR index 2)"),
            (diff_std, "7. Difference: Standard Grayscale Method"),
            (diff_numpy, "8. Difference: Red Channel Method"),
        ]

        print(f"   ✓ {len(images)} images prepared")

        # Step 10: Display
        print("\n10. Displaying images...")
        print("    Controls:")
        print("    - A or LEFT arrow:  Previous image")
        print("    - D or RIGHT arrow: Next image")
        print("    - Q: Quit\n")

        display_image_sequence(images)

        print("\n✓ Debug session complete")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if camera is not None:
            print("\n11. Disconnecting camera...")
            try:
                if camera.IsOpen():
                    camera.Close()
                print("    ✓ Disconnected")
            except:
                pass


if __name__ == "__main__":
    main()
