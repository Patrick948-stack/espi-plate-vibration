# ===============================================================================
# MANUAL EXPOSURE
# Source code from: Basler Product Documentation https://docs.baslerweb.com/exposure-time 
# Modified by: Patrick Mulikuza
# ===============================================================================
from pypylon import pylon    # module to give us control over the camera
from pypylon import genicam  # module that handles errors


def set_exposure(camera, exposure, frame_nber):
    """
    Sets a manual exposure time and grabs frame_nber frames, printing
    the exposure and mean brightness of each one.

    Parameters:
        camera     — a pylon.InstantCamera object
        exposure   — desired exposure time in microseconds (µs)
        frame_nber — how many frames to grab
    """
    # ExposureAuto must be "Off" before you can write ExposureTime manually.
    # Without this line the camera ignores your ExposureTime.Value write.
    camera.ExposureAuto.Value = "Off"

    # Write the exposure time the caller requested.
    # Unit is MICROSECONDS (µs). Higher = brighter image, lower = darker.
    camera.ExposureTime.Value = exposure

    # Read it back to confirm the camera accepted the value
    print(f"\n[Manual mode] Exposure set to: {camera.ExposureTime.Value} µs")

    print(f"\n--- Grabbing {frame_nber} frames ---\n")

    # StartGrabbingMax(n) — camera fills buffers and stops after exactly n frames
    camera.StartGrabbingMax(frame_nber)

    frame_count = 0

    while camera.IsGrabbing():
        # Block until the next frame is ready (timeout = 5000 ms)
        # ThrowException — raise an error immediately if no frame arrives in time
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grabResult.GrabSucceeded():
            frame_count += 1

            # Read the actual exposure the camera used for this frame
            current_exposure = camera.ExposureTime.Value

            # grabResult.Array is a numpy ndarray — shape (H, W) for mono cameras
            img = grabResult.Array

            # img.mean() gives the average pixel value across the whole frame
            # 0 = pure black, 255 = pure white (for 8-bit cameras)
            mean_brightness = img.mean()

            print(f"Frame {frame_count:>2}  |  "
                  f"Exposure: {current_exposure:>10.1f} µs  |  "
                  f"Mean brightness: {mean_brightness:>6.1f} / 255")
            print(f"Array image: ", img)

        else:
            print(f"Frame {frame_count + 1}: Grab failed — {grabResult.ErrorDescription}")

        # Release the buffer so the camera can reuse it.
        grabResult.Release()

    print(f"\n--- Grab complete. Final ExposureTime: {camera.ExposureTime.Value:.1f} µs ---")


def main():
    # Open the camera once here so both the limit check and set_exposure
    # share the same session — no need to connect and disconnect twice.
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()

    print("=" * 60)
    print("Camera:", camera.GetDeviceInfo().GetModelName())
    print("=" * 60)

    try:
        # Read the hardware limits — the camera tells us the safe range
        min_exp = camera.ExposureTime.Min   # Shortest possible exposure (µs)
        max_exp = camera.ExposureTime.Max   # Longest possible exposure (µs)
        print(f"\n[Manual mode] Exposure range on this camera: {min_exp} µs to {max_exp} µs")

        # Ask the user for a value and clamp it to [min_exp, max_exp] silently.
        # max(min_exp, min(user_value, max_exp)) is the standard one-line clamp.
        raw = int(input(f"Enter desired exposure time in µs ({min_exp:.0f} – {max_exp:.0f}): "))
        exposure = max(min_exp, min(raw, max_exp))

        if exposure != raw:
            print(f"Value clamped to {exposure} µs (was out of range).")

        # Ask how many frames to grab
        frame_nber = int(input("How many frames to grab? "))

        set_exposure(camera, exposure, frame_nber)

    except genicam.GenericException as e:
        # Catches: camera not found, value out of range, timeout, feature unavailable, etc.
        print("\n[ERROR] A GenICam exception occurred:")
        print(e)

    finally:
        camera.Close()
        print("\nCamera closed.")


main()
