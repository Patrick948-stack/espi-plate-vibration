import numpy as np
import cv2
from pypylon import pylon
from pypylon import genicam

def convert_image(camera, exposure, frame_nber):
    camera.ExposureAuto.Value = "Off"

    camera.ExposureTime.Value = exposure

    print(f"\n[Manual Mode] Exposure set to: {camera.ExposureTime.Value} µs")

    print(f"\n --- Grabbing {frame_nber} frames ---\n")

    camera.StartGrabbingMax(frame_nber)

    frame_count = 0
    images = []
    while camera.IsGrabbing():
        with camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException) as grabResult:
            frame_count += 1

            if grabResult.GrabSucceeded():
                img = grabResult.Array
                images.append(img)
            else:
                print(f"Frame {frame_count}: Grab failed - {grabResult.ErrorDescription}")

    print(f"\n--- Grab complete. Final ExposureTime: {camera.ExposureTime.Value:.1f} µs ---")
    if len(images) != 0:
        for i in range(len(images)):
            cv2.imwrite(f"image{i}.png", images[i])
            cv2.imshow(f"image{i}", images[i])
            cv2.waitKey(0)
            cv2.destroyAllWindows()



def main():

    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()
    print("=" * 60)
    print("Camera: ", camera.GetDeviceInfo().GetModelName())
    print("=" * 60)

    try:
        min_exp = camera.ExposureTime.Min

        max_exp = camera.ExposureTime.Max

        print(f"\n [Manual mode] Exposure range on this camera: {min_exp} µs to {max_exp} µs.")

        raw = int(input(f"Enter desired exposure time in µs ({min_exp:.0f} - {max_exp:0f}): "))

        exposure = max(min_exp, min(raw, max_exp))

        if exposure != raw:
            print(f"Value clamped to {exposure} µs (was out of range).")
        
        # Ask how many frames to grab
        frame_nber = int(input("How many frames to grab? "))

        convert_image(camera, exposure, frame_nber)

    except genicam.GenericException as e:
        # Catches: camera not found, value out of range, timeout, feature unavailable, etc.
        print("\n[ERROR] A GenICam exception occurred:")
        print(e)

    finally:
        camera.Close()
        print("\nCamera closed.")


main()


    