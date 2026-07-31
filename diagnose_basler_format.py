"""
Diagnose what pixel format the Basler camera is actually capturing.

Checks:
1. Frame shape (height, width, channels)
2. Data type (uint8, uint16, etc.)
3. Whether it's color (3 channels) or grayscale (1 channel)
4. Sample pixel values from first few pixels
"""

import sys
from pathlib import Path
import numpy as np

# Add ESPI Full Algorithm to path so we can import camera_control
project_root = Path(__file__).parent
espi_dir = project_root / "ESPI Full Algorithm"
sys.path.insert(0, str(espi_dir))

import camera_control

print("=" * 70)
print("BASLER CAMERA FORMAT DIAGNOSTIC")
print("=" * 70)

try:
    # Connect to camera
    print("\n1. Connecting to Basler camera...")
    camera = camera_control.connect_camera()
    print("   ✓ Connected")

    # Set a reasonable exposure for diagnostics
    print("\n2. Setting exposure to 1ms...")
    camera_control.set_exposure_manual(camera, exposure_s=0.001)
    print("   ✓ Exposure set")

    # Grab a single frame
    print("\n3. Grabbing a frame...")
    frame = camera_control.grab_single_frame_color_with_retry(camera)
    print("   ✓ Frame captured")

    # Disconnect
    print("\n4. Disconnecting...")
    camera_control.disconnect_camera(camera)
    print("   ✓ Disconnected")

    # Analyze the frame
    print("\n" + "=" * 70)
    print("FRAME ANALYSIS")
    print("=" * 70)

    print(f"\nFrame shape: {frame.shape}")
    print(f"Data type: {frame.dtype}")

    if len(frame.shape) == 2:
        print(f"Format: GRAYSCALE (single channel, 2D array)")
        print(f"Dimensions: {frame.shape[0]} rows × {frame.shape[1]} columns")
        num_channels = 1
    elif len(frame.shape) == 3:
        print(f"Format: COLOR ({frame.shape[2]} channels, 3D array)")
        print(f"Dimensions: {frame.shape[0]} rows × {frame.shape[1]} columns × {frame.shape[2]} channels")
        num_channels = frame.shape[2]
    else:
        print(f"Format: UNKNOWN (unexpected shape {frame.shape})")
        num_channels = None

    # Show sample pixel values
    print(f"\nSample pixel values (top-left 3×3 region):")
    if num_channels == 1:
        print("Single channel (grayscale):")
        print(frame[:3, :3])
    elif num_channels == 3:
        print("Channel 0 (B in BGR):")
        print(frame[:3, :3, 0])
        print("\nChannel 1 (G in BGR):")
        print(frame[:3, :3, 1])
        print("\nChannel 2 (R in BGR):")
        print(frame[:3, :3, 2])

    # Statistics
    print(f"\nFrame statistics:")
    print(f"  Min value: {np.min(frame)}")
    print(f"  Max value: {np.max(frame)}")
    print(f"  Mean value: {np.mean(frame):.2f}")
    print(f"  Std dev: {np.std(frame):.2f}")

    if num_channels == 3:
        print(f"\nPer-channel statistics:")
        for ch, name in enumerate(['B', 'G', 'R']):
            print(f"  Channel {ch} ({name}): min={np.min(frame[:,:,ch])}, max={np.max(frame[:,:,ch])}, mean={np.mean(frame[:,:,ch]):.2f}")

    # Conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    if num_channels == 1:
        print("❌ Camera is capturing GRAYSCALE (1 channel)")
        print("   This is why all grayscale methods produce identical results!")
        print("   Check camera_control.py for pixel format configuration.")
    elif num_channels == 3:
        print("✓ Camera is capturing COLOR (3 channels - BGR format)")
        print("   Single-channel extraction should work and show different intensities.")
    print()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
