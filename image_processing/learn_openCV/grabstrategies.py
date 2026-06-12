# =============================================================================
# Source: pypylon official GitHub repository
#   https://github.com/basler/pypylon/blob/master/samples/Grab_Strategies.py
#
# WHAT IS pypylon?
# pypylon is a free Python library made by Basler (the camera manufacturer)
# that lets you control their cameras from Python code.
# To install it: run  `pip install pypylon`  in your terminal.
# You also need to install the free "pylon" software from Basler's website:
#   https://www.baslerweb.com/en/products/software/basler-pylon-camera-software-suite/
#
# WHAT DOES THIS SCRIPT TEACH?
# When a camera captures images faster than your code can process them,
# you need to decide: which images do you keep? which do you throw away?
# That decision is called a "grab strategy".
# This script walks through the 4 grab strategies pypylon offers,
# showing what each one does and when you would use it.
# =============================================================================


# ---- IMPORTS ----------------------------------------------------------------
# An import statement loads a library so you can use its tools in your script.

import sys
# 'sys' is a built-in Python library. It is imported here as a convention
# when writing scripts that could succeed or fail (the exitCode variable below
# uses it). We don't actively call sys functions in this particular script.

import time
# 'time' is a built-in Python library. We use time.sleep() later to pause
# the script for a fraction of a second. This gives the camera enough time
# to finish capturing images before we try to read them.

from pypylon import pylon
# This imports the 'pylon' module from the pypylon library.
# Think of 'pylon' as a toolbox — all the camera functions we need are inside it.
# The word 'pylon' here is just a name; we use it to call things like:
#   pylon.InstantCamera(...)
#   pylon.GrabStrategy_OneByOne
# Alternative way to write the same import: `import pypylon.pylon as pylon`
# — they work exactly the same way, just different personal style.

from samples.imageeventprinter import ImageEventPrinter
# This imports a helper class from the pypylon samples folder.
# ImageEventPrinter watches for incoming images and prints basic info about
# each one (its number, size, timestamp) to the console — useful for debugging.
# In your own experiment code, you would replace this with code that
# actually processes or saves the image data.

from samples.configurationeventprinter import ConfigurationEventPrinter
# Another helper class from the samples folder.
# ConfigurationEventPrinter watches the camera and prints a message whenever
# something happens to it — like when it opens, closes, or starts capturing.
# Again, purely for learning/debugging purposes.


# =============================================================================
# STEP 1 — Keep track of whether the script succeeded or failed
# =============================================================================

exitCode = 0
# This variable will store 0 (success) or 1 (failure) by the end of the script.
# It is a common convention in programming: 0 = everything went fine.
# If something went wrong you would set exitCode = 1 inside an error handler
# and then call sys.exit(exitCode) at the very end to signal failure.


# =============================================================================
# STEP 2 — Find and connect to a camera
# =============================================================================

camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
# This one line does three things — let's read it from the inside out:
#
#   1. pylon.TlFactory.GetInstance()
#      TlFactory is pypylon's "camera finder". It scans your computer for any
#      Basler cameras that are plugged in (via USB, network cable, etc.).
#      GetInstance() gets that finder object ready to use.
#
#   2. .CreateFirstDevice()
#      Looks at all the cameras found and picks the very first one.
#      If no camera is plugged in, this will raise an error and stop the script.
#      Alternative: if you have multiple cameras and want a specific one,
#      you can use .EnumerateDevices() to list them all, then pick by name or
#      serial number.
#
#   3. pylon.InstantCamera(...)
#      Wraps that camera in an "InstantCamera" object — the main object you will
#      use throughout your script to control everything: open/close the camera,
#      start/stop capturing, read images, etc.
#      Alternative for controlling multiple cameras at once: pylon.InstantCameraArray(2)
#
# After this line, 'camera' is a Python object representing your physical camera.
# The camera is NOT yet turned on/open — we have only created the Python object.


# =============================================================================
# STEP 3 — Tell the camera how to behave (register configurations)
# =============================================================================

camera.RegisterConfiguration(
    pylon.SoftwareTriggerConfiguration(),   # WHAT behaviour to apply
    pylon.RegistrationMode_ReplaceAll,      # replace any existing settings
    pylon.Cleanup_Delete                    # pypylon will clean this up automatically
)
# RegisterConfiguration() tells the camera to follow a set of rules.
# Here we are applying "SoftwareTriggerConfiguration", which means:
#   "Don't capture images on your own — wait for MY command before each shot."
# In other words, we want MANUAL control over when each photo is taken.
#
# The three arguments explain HOW the rule is applied:
#
#   pylon.SoftwareTriggerConfiguration()
#     The rule itself. This switches the camera from "capture continuously"
#     to "wait for a software trigger command".
#     Other built-in rules you could use instead:
#       pylon.AcquireContinuousConfiguration()  → camera captures non-stop automatically
#       pylon.AcquireSingleFrameConfiguration() → camera captures exactly one frame then stops
#
#   pylon.RegistrationMode_ReplaceAll
#     "Remove any rules already registered and replace them with this new one."
#     Use this when you want to start fresh with a completely new behaviour.
#     Alternative: pylon.RegistrationMode_Append
#       → "Keep existing rules AND also add this one." Use this when layering
#          multiple handlers (like adding a logging handler on top).
#
#   pylon.Cleanup_Delete
#     "When this rule is no longer needed, pypylon should delete it automatically."
#     This is the safe, easy choice when you create the object right inside the call.
#     Alternative: pylon.Cleanup_None
#       → "I will delete it myself." Only use this if you stored the object
#          in a variable and want to reuse it.

camera.RegisterConfiguration(
    ConfigurationEventPrinter(),
    pylon.RegistrationMode_Append,   # APPEND — don't remove the trigger rule above
    pylon.Cleanup_Delete
)
# We are ADDING a second rule on top of the first one (hence RegistrationMode_Append).
# ConfigurationEventPrinter just prints messages when camera events happen —
# it doesn't change how the camera works, it only observes and reports.
# Notice we use Append here, not ReplaceAll, because we want BOTH rules active:
# the software trigger rule AND the event printer.

camera.RegisterImageEventHandler(
    ImageEventPrinter(),
    pylon.RegistrationMode_Append,
    pylon.Cleanup_Delete
)
# This registers a different kind of handler — an IMAGE event handler.
# The difference:
#   RegisterConfiguration()      → reacts to camera events (open, close, grab start/stop)
#   RegisterImageEventHandler()  → reacts to image events (every time a photo arrives)
# ImageEventPrinter will automatically print info about every image that comes in.
# In a real experiment, you would put your image processing or saving code here.


# =============================================================================
# STEP 4 — Print the camera model name
# =============================================================================

print("Using device ", camera.GetDeviceInfo().GetModelName())
# GetDeviceInfo() asks the camera for its identification details.
# GetModelName() pulls out the model name from those details, e.g. "acA1920-40gc".
# Other things you can get from GetDeviceInfo():
#   .GetSerialNumber() → the unique serial number of this specific camera unit
#   .GetIpAddress()    → the network address (only works for GigE network cameras)


# =============================================================================
# STEP 5 — Set how many image slots to reserve in memory
# =============================================================================

camera.MaxNumBuffer.Value = 15
# When the camera captures images, they are stored in "buffers" —
# think of each buffer as a slot in a waiting room that holds one image.
# MaxNumBuffer sets how many of these waiting-room slots are created.
# Default is 10. We are using 15 here to give a little more room.
# More slots = more images can wait before any are lost.
#
# This is how you read or write most camera settings in pypylon:
#   camera.SettingName.Value = newValue    ← to change a setting
#   current = camera.SettingName.Value     ← to read the current value
# You will see this pattern throughout the script for other settings too.


# =============================================================================
# STEP 6 — Open the camera
# =============================================================================

camera.Open()
# This establishes the actual connection to the camera hardware.
# After Open() you can read and write camera settings (exposure time, gain, etc.)
# and the SoftwareTriggerConfiguration we registered above will now take effect.
# You must call Open() before you can change any camera settings.
# Note: if you skip Open() and call StartGrabbing() directly, pypylon will
# open the camera for you automatically — but opening manually first is better
# practice because errors (like wrong settings) appear sooner and are easier to fix.


# =============================================================================
# =============================================================================
# GRAB STRATEGY 1 — OneByOne (the default, safest strategy)
# =============================================================================
# =============================================================================
#
# CONCEPT: Imagine the camera puts each photo in a line (a queue).
# OneByOne means every single photo joins that line and waits its turn.
# Your code picks them up one at a time, in the same order they were taken.
# No photo is ever thrown away — they all wait patiently.
#
# GOOD FOR: experiments where you cannot afford to miss a single frame
#           (e.g. tracking a fast event, recording for offline analysis).
# WATCH OUT: if your code is slow and the camera is fast, the line gets
#            very long. When all 15 buffer slots are full, the oldest ones
#            start getting overwritten — you lose frames silently.
# =============================================================================

print("Grab using the GrabStrategy_OneByOne default strategy:")

camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
# StartGrabbing() turns on image capture.
# The argument tells it which grab strategy to use.
# From this point, the camera is running in the background, ready to take photos
# each time we send a trigger command.
# The four strategy options are:
#   pylon.GrabStrategy_OneByOne       → keep every image in order (this one)
#   pylon.GrabStrategy_LatestImageOnly → keep only the most recent image
#   pylon.GrabStrategy_LatestImages    → keep the N most recent images
#   pylon.GrabStrategy_UpcomingImage   → capture one image per retrieve call

# --- Send 3 trigger commands -------------------------------------------------

for i in range(3):
    # range(3) means: repeat 3 times, with i = 0, then 1, then 2.
    # We send one trigger each loop iteration, so the camera takes 3 photos total.

    if camera.WaitForFrameTriggerReady(200, pylon.TimeoutHandling_ThrowException):
        # Before firing the trigger, we check if the camera is actually ready.
        # WaitForFrameTriggerReady() asks: "Are you ready for the next trigger?"
        # 200 = wait up to 200 milliseconds for the camera to be ready.
        # If the camera becomes ready within that time, we get True and proceed.
        #
        # TimeoutHandling_ThrowException means:
        #   "If 200ms passes and the camera is STILL not ready, crash with an error."
        #   This is the safe choice — you want to know if something is wrong.
        # Alternative: pylon.TimeoutHandling_Return
        #   → Instead of crashing, just return False so you can handle it yourself.

        camera.ExecuteSoftwareTrigger()
        # This is the actual trigger command — "take a photo NOW".
        # The camera exposes the sensor and stores the result in one of the
        # buffer slots we reserved. Your code doesn't receive it yet;
        # it just sits in the waiting line until we retrieve it below.

# --- Give the camera a moment to finish --------------------------------------

time.sleep(0.2)
# We pause for 0.2 seconds (200 milliseconds).
# Why? Because the camera works asynchronously — after we fire the trigger,
# the image travels from the camera to your computer in the background.
# Waiting gives that transfer time to complete so the images are ready
# when we check the queue next.

# --- Check if images are waiting ---------------------------------------------

if camera.GetGrabResultWaitObject().Wait(0):
    print("Grab results wait in the output queue.")
# This is a quick check: "Are there any images sitting in the queue right now?"
# GetGrabResultWaitObject() returns a special object that knows when images are waiting.
# .Wait(0) checks instantly (0 = don't wait at all) and returns True if images are there.
# We are not taking any images out yet — just peeking.
# Alternative: .Wait(5000) would wait up to 5 seconds for an image to appear,
# which is useful when you want to block until something arrives.

# --- Retrieve all images from the queue --------------------------------------

buffersInQueue = 0
# This counter will track how many images we successfully pulled out.

while camera.RetrieveResult(0, pylon.TimeoutHandling_Return):
    # RetrieveResult() takes ONE image out of the queue and returns it.
    # 0 = don't wait; if nothing is there, return immediately.
    # TimeoutHandling_Return = if nothing is there, return an empty result
    #   (instead of crashing). An empty result is "falsy" in Python,
    #   so the while loop stops automatically when the queue is empty.
    #
    # The returned object is a GrabResult — it contains the actual pixel data
    # plus metadata (frame number, timestamp, width, height, etc.).
    # To get the pixel data as a NumPy array you would write:
    #   grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    #   if grabResult.GrabSucceeded():
    #       image_array = grabResult.GetArray()   # shape: (height, width) for mono
    #
    # IMPORTANT: while you hold onto a GrabResult, that buffer slot is "occupied"
    # and can't be reused by the camera. Release it (let it go out of scope or
    # call grabResult.Release()) when you're done with it.
    buffersInQueue += 1

print("Retrieved ", buffersInQueue, " grab results from output queue.")
# With OneByOne strategy and 3 triggers, all 3 images are saved → prints "3".

camera.StopGrabbing()
# Turns off image capture. Frees all buffer slots from memory.
# Always call this before switching to a different grab strategy,
# or before closing the camera.


# =============================================================================
# GRAB STRATEGY 2 — LatestImageOnly
# =============================================================================
#
# CONCEPT: The waiting line can only hold ONE photo at a time.
# If a new photo arrives while another is already waiting, the old one is
# thrown away and the new one takes its place. Only the very latest photo survives.
#
# GOOD FOR: live display on a screen, real-time monitoring, or any situation
#           where stale images are useless and you always want the freshest one.
#           Example: a live video feed where old frames are irrelevant.
# RESULT:   Of 3 triggered photos, only 1 will survive in the queue.
# =============================================================================

print("Grab using strategy GrabStrategy_LatestImageOnly:")

camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

for i in range(3):
    if camera.WaitForFrameTriggerReady(200, pylon.TimeoutHandling_ThrowException):
        camera.ExecuteSoftwareTrigger()
# Same as before: send 3 trigger commands, taking 3 photos.
# But this time, because the queue can only hold 1, photos 1 and 2 will be
# discarded as newer ones arrive. Only photo 3 will be waiting when we check.

time.sleep(0.2)
# Wait for the last image to finish transferring to the computer.

if camera.GetGrabResultWaitObject().Wait(0):
    print("A grab result waits in the output queue.")
# Peeking at the queue — there should be exactly 1 result waiting.

buffersInQueue = 0

while True:
    # while True creates an infinite loop. We must break out of it ourselves
    # using the 'break' keyword when we decide to stop.
    # This is a common Python pattern when you don't know ahead of time
    # how many times you need to loop.

    grabResult = camera.RetrieveResult(0, pylon.TimeoutHandling_Return)
    # Try to take one image out of the queue.
    # If the queue is empty, grabResult will be "invalid" (empty).

    if not grabResult.IsValid():
        break
    # IsValid() asks: "Did we actually get an image, or is this an empty result?"
    # If it's empty (IsValid() is False), we stop the loop.
    # Note: a "valid" result just means something came back — it doesn't
    # guarantee the photo itself was captured correctly. To check that, use:
    #   grabResult.GrabSucceeded()   → True if the photo is good, False if corrupted/failed

    print("Skipped ", grabResult.GetNumberOfSkippedImages(), " images.")
    # GetNumberOfSkippedImages() tells you how many photos were thrown away
    # to make room for this one. With 3 triggers and a queue of 1,
    # 2 photos were discarded → this will print "2".
    buffersInQueue += 1

print("Retrieved ", buffersInQueue, " grab result from output queue.")
# Prints "1" — only the last of the 3 triggered photos survived.

camera.StopGrabbing()


# =============================================================================
# GRAB STRATEGY 3 — LatestImages (keep the N most recent photos)
# =============================================================================
#
# CONCEPT: Like LatestImageOnly, but the waiting line can hold more than 1 photo.
# You choose how many slots the line has (e.g. 2). When a 3rd photo arrives,
# the oldest of the 2 waiting is discarded to make room.
# You always have the N most recent photos available.
#
# GOOD FOR: situations where you need a small history of recent frames —
#           for example, comparing the current frame to the previous one,
#           or buffering 2-3 frames for a rolling average.
# =============================================================================

print("Grab using strategy GrabStrategy_LatestImages:")

camera.OutputQueueSize.Value = 2
# This sets the queue to hold 2 photos at most.
# When a 3rd arrives, the oldest of the 2 waiting is automatically dropped.
# You can change this number while the camera is grabbing — it updates live.
# Using the same .Value pattern as MaxNumBuffer earlier.

camera.StartGrabbing(pylon.GrabStrategy_LatestImages)

for i in range(3):
    if camera.WaitForFrameTriggerReady(200, pylon.TimeoutHandling_ThrowException):
        camera.ExecuteSoftwareTrigger()
# 3 photos triggered. With queue size 2, photo 1 is discarded when photo 3 arrives.
# Photos 2 and 3 will be waiting when we retrieve.

time.sleep(0.2)

if camera.GetGrabResultWaitObject().Wait(0):
    print("Grab results wait in the output queue.")

buffersInQueue = 0
while True:
    grabResult = camera.RetrieveResult(0, pylon.TimeoutHandling_Return)
    if not grabResult.IsValid():
        break

    if grabResult.GetNumberOfSkippedImages():
        # Only print if at least one photo was actually skipped.
        # Without this if-check, we'd print "Skipped 0 images" for every
        # result that didn't have anything skipped before it — just noisy output.
        print("Skipped ", grabResult.GetNumberOfSkippedImages(), " image.")

    buffersInQueue += 1

print("Retrieved ", buffersInQueue, " grab results from output queue.")
# With queue size 2 and 3 triggers this prints "2".

# --- Showing the relationship between strategies -----------------------------

camera.OutputQueueSize.Value = 1
# Setting queue size to 1 makes LatestImages behave exactly like LatestImageOnly.
# They become identical: only 1 image ever waits in the queue.

camera.OutputQueueSize.Value = camera.MaxNumBuffer.Value
# Setting queue size to MaxNumBuffer (15) makes LatestImages behave exactly
# like OneByOne. Every image is kept because the queue is large enough to
# hold all of them before any get dropped.
# camera.MaxNumBuffer.Value reads back the number we set earlier (15).

camera.StopGrabbing()


# =============================================================================
# GRAB STRATEGY 4 — UpcomingImage (capture on demand, one at a time)
# =============================================================================
#
# CONCEPT: Instead of the camera continuously filling a queue, nothing happens
# until YOUR code asks for a photo. The moment you call RetrieveResult(),
# the camera captures the very NEXT frame and hands it directly to you.
# There is no pre-filled queue — you ask, it shoots, you receive.
#
# GOOD FOR: situations where timing matters precisely — you want the image
#           taken at the exact moment your code requests it, not earlier.
#           Example: "capture an image AFTER I move this motor to position X."
#
# LIMITATION: this strategy does NOT work with USB cameras. Only GigE (network)
#             and Camera Link cameras support it.
# =============================================================================

if not camera.IsUsb():
    # camera.IsUsb() returns True if the camera is connected via USB.
    # We only run this section if it is NOT USB, because UpcomingImage
    # would cause an error on USB cameras.
    # The 'not' keyword flips the result: True becomes False and vice versa.
    # So `if not camera.IsUsb()` means "if this is NOT a USB camera, proceed."

    print("Grab using the GrabStrategy_UpcomingImage strategy:")

    pylon.AcquireContinuousConfiguration().OnOpened(camera)
    # Up until now we had SoftwareTriggerConfiguration active —
    # the camera was waiting for our trigger commands.
    # UpcomingImage works differently: the camera must be in continuous mode
    # (streaming freely) so that when we ask for a frame, one is ready immediately.
    # AcquireContinuousConfiguration() switches the camera to continuous mode.
    # Calling .OnOpened(camera) directly is a shortcut to apply this change
    # to a camera that's already open, without re-registering everything.

    camera.StartGrabbing(pylon.GrabStrategy_UpcomingImage)
    # Start capturing with the UpcomingImage strategy.
    # At this point NO images are being buffered yet — the camera is streaming
    # but nothing is being saved until we specifically ask for one below.

    grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    # RetrieveResult() here works differently than before.
    # With UpcomingImage, calling this does two things in sequence:
    #   1. It tells the camera "prepare a slot for the next incoming frame"
    #   2. It waits until that frame arrives and returns it to you
    # 5000 = wait up to 5000 milliseconds (5 seconds) for the frame to arrive.
    # TimeoutHandling_ThrowException = if nothing arrives in 5 seconds, crash
    #   with an error (because that's abnormal and we want to know about it).
    #
    # After this line, grabResult contains one captured image.
    # To read the pixel data:
    #   if grabResult.GrabSucceeded():
    #       image = grabResult.GetArray()   # NumPy array of pixel values
    #       # For a mono (greyscale) camera: image.shape = (height, width)
    #       # For a colour camera:           image.shape = (height, width, 3)

    time.sleep(0.2)
    # We pause briefly. During this pause, the camera keeps streaming frames,
    # but because we haven't called RetrieveResult() again, there are no
    # slots for those frames — they pass by and are discarded.
    # This is intentional: UpcomingImage only captures when YOU ask for it.

    if not camera.GetGrabResultWaitObject().Wait(0):
        print("No grab result waits in the output queue.")
    # After the sleep, we check the queue — it should be empty.
    # This confirms the UpcomingImage behaviour: no new frames are buffered
    # between your RetrieveResult() calls.
    # The 'not' here means: "if the queue is NOT signalled (i.e. empty), print this."

    camera.StopGrabbing()
    # Always stop grabbing to release resources when you're done with a session.


# =============================================================================
# QUICK REFERENCE — Which strategy should I use?
# =============================================================================
#
#   OneByOne         → You need EVERY single frame. Nothing can be missed.
#                      (e.g. recording an experiment for full playback later)
#
#   LatestImageOnly  → You only care about the CURRENT moment, not the past.
#                      (e.g. live monitoring display, real-time feedback loop)
#
#   LatestImages     → You want a small recent history — the last N frames.
#                      (e.g. comparing current to previous, rolling averages)
#
#   UpcomingImage    → You need the frame taken at a SPECIFIC moment in your code.
#                      (e.g. capture after hardware moves, precise timing)
#                      Only works on GigE and Camera Link cameras — not USB.
#
# For further reading:
#   pypylon GitHub:  https://github.com/basler/pypylon
#   pylon SDK docs:  https://docs.baslerweb.com/
# =============================================================================
