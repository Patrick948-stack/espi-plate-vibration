from pypylon import genicam


def set_exposure_manual(camera, exposure_us: float):
    """
    Turn off auto-exposure and set a specific exposure time.
    Returns the actual exposure time set.
    """
    # Disable auto exposure — required before ExposureTime.Value can be written.
    # Without this, the camera ignores the manual value.
    camera.ExposureAuto.Value = "Off"

    # Clamp the requested value to the hardware limits so we never write
    # a value the camera will reject with a GenICam exception.
    exposure_us = max(camera.ExposureTime.Min, min(exposure_us, camera.ExposureTime.Max))

    camera.ExposureTime.Value = exposure_us

    # Read back the value the camera actually accepted (may differ slightly
    # due to hardware increment rounding).
    actual = camera.ExposureTime.Value
    print(f"[Manual] Exposure set to: {actual} µs")
    return actual


def set_exposure_auto(camera):
    """
    Set exposure to auto (continuous).
    """
    # Give the auto algorithm the full hardware range to work within.
    camera.AutoExposureTimeLowerLimit.Value = camera.AutoExposureTimeLowerLimit.Min
    camera.AutoExposureTimeUpperLimit.Value = camera.AutoExposureTimeUpperLimit.Max

    # Target brightness 0.5 = mid-grey, a neutral default.
    camera.AutoTargetBrightness.Value = 0.5

    # Use ROI1 for brightness measurement so the algorithm focuses on the
    # center region rather than the full frame (default ROI position).
    camera.AutoFunctionROISelector.Value = "ROI1"
    camera.AutoFunctionROIUseBrightness.Value = True

    # "Continuous" — camera keeps adjusting exposure on every frame.
    camera.ExposureAuto.Value = "Continuous"
    print("[Auto] ExposureAuto set to Continuous.")


def set_pixel_format(camera, pixel_format: str) -> None:
    """
    Set the pixel format on the camera (e.g. "Mono8", "Mono12", "RGB8").
    """
    # ExposureAuto and grabbing must be stopped before changing pixel format
    # on some cameras, but pypylon will raise a GenICam exception if that is
    # required — the caller is responsible for stopping grab first.
    camera.PixelFormat.Value = pixel_format
    print(f"[set_pixel_format] Pixel format set to: {camera.PixelFormat.Value}")


def get_camera_info(camera):
    """
    Returns a dictionary of current camera settings.
    """
    try:
        info = {
            "model":          camera.GetDeviceInfo().GetModelName(),
            "serial":         camera.GetDeviceInfo().GetSerialNumber(),
            "width":          camera.Width.Value,
            "height":         camera.Height.Value,
            "exposure_us":    camera.ExposureTime.Value,
            "exposure_auto":  camera.ExposureAuto.Value,
            "gain":           camera.Gain.Value,
            "pixel_format":   camera.PixelFormat.Value,
        }
    except genicam.GenericException as e:
        print(f"Could not read one or more camera settings: {e}")
        info = {}
    return info
