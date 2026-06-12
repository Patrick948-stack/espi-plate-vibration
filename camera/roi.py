from pypylon import genicam


def set_capture_roi(camera, x: int, y: int, width: int, height: int) -> None:
    """
    Set the camera's Region of Interest (ROI) — only this area is read out
    each frame, which increases frame rate and reduces data transfer.

    Args:
        x, y          — top-left corner of the ROI in pixels
        width, height — dimensions of the ROI in pixels

    All values are clamped to hardware limits and aligned to the camera's
    required increment (Inc) automatically.
    """
    try:
        # Offsets must be set to 0 before changing Width/Height, otherwise
        # the new dimensions might push the ROI outside the sensor boundary.
        camera.OffsetX.Value = 0
        camera.OffsetY.Value = 0

        # Clamp and align width/height to the camera's increment grid.
        cam_width  = camera.Width.Max
        cam_height = camera.Height.Max
        w_inc = camera.Width.Inc
        h_inc = camera.Height.Inc
        x_inc = camera.OffsetX.Inc
        y_inc = camera.OffsetY.Inc

        width  = max(camera.Width.Min,  min(width,  cam_width)  // w_inc * w_inc)
        height = max(camera.Height.Min, min(height, cam_height) // h_inc * h_inc)
        x      = min(x // x_inc * x_inc, cam_width  - width)
        y      = min(y // y_inc * y_inc, cam_height - height)

        camera.Width.Value   = width
        camera.Height.Value  = height
        camera.OffsetX.Value = x
        camera.OffsetY.Value = y

        print(f"[set_capture_roi] ROI set to x={x}, y={y}, w={width}, h={height}")

    except genicam.GenericException as e:
        print(f"[set_capture_roi] Error setting ROI: {e}")


def reset_capture_roi(camera) -> None:
    """
    Reset the ROI to the full sensor area.
    """
    try:
        # Offsets must be zeroed before restoring full Width/Height.
        camera.OffsetX.Value = 0
        camera.OffsetY.Value = 0
        camera.Width.Value   = camera.Width.Max
        camera.Height.Value  = camera.Height.Max

        print(f"[reset_capture_roi] ROI reset to full sensor "
              f"({camera.Width.Value} x {camera.Height.Value})")

    except genicam.GenericException as e:
        print(f"[reset_capture_roi] Error resetting ROI: {e}")
