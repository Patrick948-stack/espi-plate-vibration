"""
Check what pixel formats your Basler camera actually supports.
"""

import sys
from pathlib import Path

# Add ESPI Full Algorithm to path (this script now lives one level deeper,
# in Learning/, so the project root is one parent further up than before)
project_root = Path(__file__).parent.parent
espi_dir = project_root / "ESPI Full Algorithm"
sys.path.insert(0, str(espi_dir))

import camera_control

print("=" * 70)
print("BASLER CAMERA - AVAILABLE PIXEL FORMATS")
print("=" * 70)

try:
    # Connect WITHOUT setting a format (use default)
    print("\nConnecting to Basler camera (default format)...")
    from pypylon import pylon

    device = pylon.TlFactory.GetInstance().CreateFirstDevice()
    camera = pylon.InstantCamera(device)
    camera.Open()

    print(f"✓ Connected to: {camera.GetDeviceInfo().GetModelName()}")

    # Get current format
    current = camera.PixelFormat.Value
    print(f"\nCurrent pixel format: {current}")

    # List all available formats
    print("\nAvailable pixel formats:")
    try:
        # Get the available values for PixelFormat
        available = camera.PixelFormat.Symbolics
        for i, fmt in enumerate(available, 1):
            print(f"  {i}. {fmt}")
    except Exception as e:
        print(f"  Could not enumerate formats: {e}")

    # Try setting BayerRG8 and verify
    print("\nTesting BayerRG8 format...")
    try:
        camera.PixelFormat.Value = "BayerRG8"
        result = camera.PixelFormat.Value
        print(f"  Set to: BayerRG8")
        print(f"  Camera reports: {result}")
        if "BayerRG8" in str(result):
            print("  ✓ BayerRG8 is supported!")
        else:
            print(f"  ✗ Format mismatch: requested BayerRG8, got {result}")
    except Exception as e:
        print(f"  ✗ BayerRG8 not supported: {e}")

    # Try RGB8
    print("\nTesting RGB8 format...")
    try:
        camera.PixelFormat.Value = "RGB8"
        result = camera.PixelFormat.Value
        print(f"  Set to: RGB8")
        print(f"  Camera reports: {result}")
        if "RGB8" in str(result):
            print("  ✓ RGB8 is supported!")
        else:
            print(f"  ✗ Format mismatch: requested RGB8, got {result}")
    except Exception as e:
        print(f"  ✗ RGB8 not supported: {e}")

    # Reset to Mono8
    print("\nResetting to Mono8...")
    camera.PixelFormat.Value = "Mono8"
    print(f"  Format: {camera.PixelFormat.Value}")

    camera.Close()
    print("\n✓ Done")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
