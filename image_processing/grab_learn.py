from pypylon import pylon
from pypylon import genicam

import sys

#1. Find the camera and get it

camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
camera.Open()

#get camera name/identify camera
print("Device Model Name", camera.GetDeviceInfo().GetModelName())

#2 Ask Camera to take images
nberOfImagesToGrab = 15
camera.StartGrabbingMax(nberOfImagesToGrab)
while camera.IsGrabbing():
    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    print(grabResult)

grabResult.Release()
camera.Close()


