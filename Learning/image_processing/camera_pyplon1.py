# ===============================================================================
# PYPYLON LIBRARY - KEY CONCEPTS & SYNTAX GUIDE
# ===============================================================================
# pypylon is Basler's official Python wrapper for their pylon Camera SDK.
# It gives you Python access to Basler cameras for image acquisition,
# camera configuration, and pixel data processing.
#
# TWO MAIN MODULES:
#   pylon   — camera control: open, configure, grab images, close
#   genicam — GenICam standard: error types, feature access rules
#
# Install:  pip install pypylon
# Docs:     https://github.com/basler/pypylon
# ===============================================================================

from pypylon import pylon    # Core module: camera objects, grabbing, factories
from pypylon import genicam  # GenICam module: standard exceptions and feature types

import sys

# --- CONSTANTS ---
countOfImagesToGrab = 100  # How many frames to capture before stopping
exitCode = 0               # Program exit status (0 = success, 1 = error)


# ===============================================================================
# PATTERN: always wrap pypylon code in try/except genicam.GenericException
# genicam.GenericException is the base class for ALL pypylon/GenICam errors.
# This catches things like: camera not found, timeout, communication failure,
# feature out of range, etc.
# ===============================================================================
try:

    # ---------------------------------------------------------------------------
    # STEP 1: TRANSPORT LAYER FACTORY  —  pylon.TlFactory
    # ---------------------------------------------------------------------------
    # The TlFactory (Transport Layer Factory) is the entry point that discovers
    # cameras connected to your computer, regardless of interface type
    # (USB3, GigE, Camera Link, etc.).
    #
    # pylon.TlFactory.GetInstance()
    #   Returns the singleton TlFactory object. There is only ever ONE factory
    #   per process — GetInstance() gives you access to it.
    #
    # .CreateFirstDevice()
    #   Scans all transport layers and returns a DeviceInfo object for the
    #   first camera it finds. Raises an exception if no camera is connected.
    #   Other options:
    #     .CreateDevice(deviceInfo)   — open a specific camera by its DeviceInfo
    #     .EnumerateDevices()         — list ALL connected cameras as a tuple
    # ---------------------------------------------------------------------------
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

    # ---------------------------------------------------------------------------
    # STEP 2: InstantCamera  —  pylon.InstantCamera
    # ---------------------------------------------------------------------------
    # InstantCamera is the main high-level class you will use for everything.
    # It wraps the low-level camera device and provides:
    #   - feature access (width, height, exposure, gain, ...)
    #   - buffer management (automatically allocates/recycles grab buffers)
    #   - grab loop helpers (StartGrabbingMax, RetrieveResult, IsGrabbing)
    #
    # The argument to InstantCamera() is the device created by the factory above.
    # ---------------------------------------------------------------------------

    # .Open() — establishes the communication session with the camera.
    # You MUST call Open() before accessing features or grabbing images.
    # Pair it with .Close() when you're done.
    camera.Open()

    # ---------------------------------------------------------------------------
    # STEP 3: DEVICE INFO  —  camera.GetDeviceInfo()
    # ---------------------------------------------------------------------------
    # GetDeviceInfo() returns a CDeviceInfo object describing the camera.
    # Useful methods on it:
    #   .GetModelName()    — human-readable model string, e.g. "acA1920-40uc"
    #   .GetSerialNumber() — unique serial number string
    #   .GetFriendlyName() — friendly display name
    #   .GetIpAddress()    — IP address (GigE cameras only)
    # ---------------------------------------------------------------------------
    print("Using device ", camera.GetDeviceInfo().GetModelName())

    # ---------------------------------------------------------------------------
    # STEP 4: FEATURE ACCESS  —  camera.<FeatureName>.Value / .Min / .Max / .Inc
    # ---------------------------------------------------------------------------
    # pypylon exposes every camera parameter as a Python attribute on the camera
    # object. These are GenICam "nodes" — typed properties that map directly to
    # hardware registers.
    #
    # Every numeric feature has four sub-properties:
    #   .Value  — current value (read or write)
    #   .Min    — minimum allowed value (hardware limit, read-only)
    #   .Max    — maximum allowed value (hardware limit, read-only)
    #   .Inc    — increment step (value must be a multiple of Inc, read-only)
    #
    # Common features:
    #   camera.Width          — image width in pixels
    #   camera.Height         — image height in pixels
    #   camera.ExposureTime   — exposure time in microseconds
    #   camera.Gain           — gain in dB
    #   camera.PixelFormat    — pixel format string (e.g. "Mono8", "RGB8")
    #   camera.AcquisitionFrameRate — frames per second
    #
    # IMPORTANT: you cannot set a value outside [Min, Max] or off the Inc grid.
    # Always validate before writing to avoid a GenICam exception.
    # ---------------------------------------------------------------------------
    new_width = camera.Width.Value - camera.Width.Inc  # Step down by one increment
    if new_width >= camera.Width.Min:                  # Only set if still in range
        camera.Width.Value = new_width

    # ---------------------------------------------------------------------------
    # STEP 5: BUFFER POOL  —  camera.MaxNumBuffer
    # ---------------------------------------------------------------------------
    # pypylon pre-allocates a pool of memory buffers that the camera fills with
    # raw pixel data during acquisition. MaxNumBuffer controls how many buffers
    # exist in that pool at any one time.
    #
    # More buffers = more frames can be queued before you must retrieve them.
    # Fewer buffers = less RAM used.
    # Default is 10. Setting it to 5 here reduces memory usage for this demo.
    #
    # If the camera fills all buffers before your code retrieves them, the next
    # incoming frame is dropped (grab failure). Increase MaxNumBuffer if you
    # see missed frames under load.
    # ---------------------------------------------------------------------------
    camera.MaxNumBuffer.Value = 5

    # ---------------------------------------------------------------------------
    # STEP 6: START GRABBING  —  camera.StartGrabbingMax(n)
    # ---------------------------------------------------------------------------
    # Begins image acquisition. The camera starts filling buffers immediately.
    #
    # camera.StartGrabbingMax(n)
    #   Grabs exactly n images then stops automatically.
    #   StopGrabbing() is called internally once n images are retrieved.
    #
    # Other grab strategies (passed as a second argument):
    #   pylon.GrabStrategy_OneByOne       — FIFO queue, default, no frames skipped
    #   pylon.GrabStrategy_LatestImageOnly — always return the most recent frame,
    #                                        discard older buffered frames
    #   pylon.GrabStrategy_LatestImages   — keep the N most recent frames
    #
    # For free-running continuous acquisition (no limit), use:
    #   camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
    # and call camera.StopGrabbing() manually when done.
    # ---------------------------------------------------------------------------
    camera.StartGrabbingMax(countOfImagesToGrab)

    # ---------------------------------------------------------------------------
    # STEP 7: GRAB LOOP  —  camera.IsGrabbing()
    # ---------------------------------------------------------------------------
    # IsGrabbing() returns True while the camera is actively acquiring frames
    # and there are still frames left to retrieve.
    # It returns False when:
    #   - StartGrabbingMax limit has been reached and all results retrieved, OR
    #   - StopGrabbing() was called manually.
    # This is the standard pattern for driving an acquisition loop.
    # ---------------------------------------------------------------------------
    while camera.IsGrabbing():

        # -----------------------------------------------------------------------
        # STEP 8: RETRIEVE RESULT  —  camera.RetrieveResult(timeout, handling)
        # -----------------------------------------------------------------------
        # Waits for the next filled buffer and returns a GrabResult object.
        #
        # Arguments:
        #   timeout (int) — milliseconds to wait for a frame before timing out.
        #                   5000 ms = wait up to 5 seconds.
        #
        #   pylon.TimeoutHandling_ThrowException
        #     If timeout expires without a frame, raise a TimeoutException.
        #     Use this when a timeout means something is wrong and you want to
        #     stop immediately.
        #
        #   pylon.TimeoutHandling_Return
        #     If timeout expires, return a GrabResult with GrabSucceeded()==False
        #     instead of raising. Use this when a timeout is acceptable and you
        #     want to keep the loop running.
        # -----------------------------------------------------------------------
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        # -----------------------------------------------------------------------
        # STEP 9: GRAB RESULT  —  grabResult object
        # -----------------------------------------------------------------------
        # The GrabResult (technically a CGrabResultPtr — a smart pointer) holds:
        #   .GrabSucceeded()    — bool: True if the frame was captured without error
        #   .Width              — image width in pixels for this specific frame
        #   .Height             — image height in pixels for this specific frame
        #   .Array              — the pixel data as a numpy ndarray (shape: HxW or HxWxC)
        #   .ErrorCode          — integer error code if GrabSucceeded() is False
        #   .ErrorDescription   — human-readable error string
        #   .PixelType          — pixel format enum value
        #   .BlockID            — frame counter (increments each acquisition)
        #   .TimeStamp          — hardware timestamp from the camera
        #
        # SMART POINTER BEHAVIOUR:
        # grabResult is a smart pointer. The underlying buffer is LOCKED and cannot
        # be reused by the camera until you call grabResult.Release() (see Step 10).
        # If you forget to release, the buffer pool drains and acquisition stalls.
        # -----------------------------------------------------------------------
        if grabResult.GrabSucceeded():
            # Access image dimensions for this frame
            print("SizeX: ", grabResult.Width)
            print("SizeY: ", grabResult.Height)
            print("Array: ", grabResult.Array)
            print("Pixel Type: ", grabResult.PixelType)
            print("BlockID: ", grabResult.BlockID)
            print("Time Stamp: ", grabResult.TimeStamp)

            # .Array returns a numpy ndarray — no extra conversion needed.
            # Shape is (Height, Width) for mono cameras (grayscale).
            # Shape is (Height, Width, 3) for color cameras (RGB/BGR).
            # dtype is uint8 for 8-bit formats, uint16 for 10/12/16-bit formats.
            # You can pass this directly to OpenCV, matplotlib, numpy, etc.
            img = grabResult.Array
            print("Gray value of first pixel: ", img[0, 0])  # Row 0, Column 0

        else:
            # Grab failed — print the error details and continue the loop
            print("Error: ", grabResult.ErrorCode, grabResult.ErrorDescription)

        # -----------------------------------------------------------------------
        # STEP 10: RELEASE THE BUFFER  —  grabResult.Release()
        # -----------------------------------------------------------------------
        # Returns the underlying buffer back to the pool so the camera can reuse
        # it for the next incoming frame. ALWAYS call this inside the loop,
        # whether the grab succeeded or not.
        #
        # If you do not release, the camera fills all MaxNumBuffer buffers,
        # runs out of space, and subsequent grabs will fail.
        #
        # Alternatively, the buffer is auto-released when grabResult goes out
        # of scope (smart pointer destructor), but explicit Release() is safer
        # and more readable.
        # -----------------------------------------------------------------------
        grabResult.Release()

    # .Close() — ends the communication session and releases camera resources.
    # Always pair with .Open(). Safe to call even if grabbing has already stopped.
    camera.Close()


# ===============================================================================
# EXCEPTION HANDLING  —  genicam.GenericException
# ===============================================================================
# genicam.GenericException is the root exception for all GenICam/pypylon errors.
# Catching it here handles:
#   - No camera found (TlFactory.CreateFirstDevice failed)
#   - Grab timeout  (RetrieveResult timed out with ThrowException mode)
#   - Feature access violation (writing a value out of range)
#   - Communication errors (USB disconnect, GigE packet loss)
#
# The exception object `e` has a .what() method and prints a descriptive message.
# ===============================================================================
except genicam.GenericException as e:
    print("An exception occurred.")
    print(e)
    exitCode = 1

sys.exit(exitCode)
