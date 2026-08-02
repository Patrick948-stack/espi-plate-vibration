# camera/connection.py - Low-Level Camera Connection

## Purpose

This file provides the lowest-level functions to connect to and disconnect from a Basler camera using pypylon. It handles the initial communication handshake with the camera hardware.

This is the foundation that all other camera control functions build on top of.

## Functions

### connect_camera()

Finds and opens the first available Basler camera.

**What it does:**
1. Use pylon.TlFactory (Transport Layer Factory) to scan for connected cameras
2. Check all transport layers: USB3, GigE, etc.
3. Return the first camera device found
4. Wrap it in a pylon.InstantCamera object
5. Open the communication session
6. Print the camera model name

**Returns:** 
- Camera object (pylon.InstantCamera) if successful
- None if no camera found

**Why this name:**
- TlFactory = Transport Layer Factory
- It scans across all connection types and finds the first device
- This is the "factory" that creates device objects

**Example:**
```python
camera = connect_camera()
if camera is None:
    print("No camera found")
else:
    # Use camera
    disconnect_camera(camera)
```

### disconnect_camera(camera)

Safely closes the connection to the camera.

**What it does:**
1. Check if the camera is currently grabbing frames
2. If yes, stop the grab sequence
3. Close the communication session
4. Free all camera resources
5. Print disconnect message

**Why important:**
If you skip this step, the camera can stay locked and refuse the next connection attempt until it is power-cycled. This is the most common cause of "camera won't connect" errors.

**Example:**
```python
try:
    # ... do work with camera ...
finally:
    disconnect_camera(camera)
```

## Under the Hood: What pylon Is

pypylon is Basler's official Python SDK (Software Development Kit). It provides:

1. **TlFactory** (Transport Layer Factory)
   - Scans for connected cameras
   - Handles USB3, GigE, and other connections
   - Returns device objects

2. **InstantCamera**
   - High-level object representing the connected camera
   - Handles feature access (exposure, gain, pixel format)
   - Manages buffer allocation for image data
   - Provides frame grabbing functions

3. **GrabResult**
   - Returned when you grab a frame
   - Contains the image array
   - Provides grab status (succeeded or failed)

## Typical Error Scenarios

### Camera Not Found

**Symptoms:**
- connect_camera() returns None
- "Could not connect to camera: No device found"

**Causes:**
1. Camera is not plugged in
2. Camera is powered off
3. USB cable is loose
4. Camera driver not installed (Windows)
5. Different USB port than expected

**Fix:**
1. Check physical cable connection
2. Check camera power indicator
3. Try a different USB port
4. Reinstall drivers if needed

### Camera Already In Use

**Symptoms:**
- connect_camera() returns None
- "Could not connect to camera: Camera in use by another session"

**Causes:**
1. Another Python script is using the camera
2. pylon Viewer (Basler's GUI tool) is open and connected
3. Previous script crashed without disconnecting

**Fix:**
1. Close all other programs using the camera
2. Wait a moment for the previous session to time out
3. If stuck, unplug and replug the camera

### Camera Becomes Unresponsive

**Symptoms:**
- Initial connection works
- Frame grab times out or returns garbage data
- "TimeoutHandling_ThrowException"

**Causes:**
1. USB cable disconnected mid-operation
2. Camera firmware issue
3. USB hub overload (too many devices)
4. Power supply to camera is failing

**Fix:**
1. Check USB cable connection
2. Try a different USB port directly on computer
3. Reduce other USB devices
4. Power cycle the camera

## Related Files

This is the lowest layer. Files that use these functions:

- camera/capture.py - Builds on connection to grab frames
- camera/settings.py - Builds on connection to adjust camera parameters
- camera_control.py - High-level functions combining connection, settings, capture
- capture_and_display.py - Uses connection for real-time preview
- run_experiment.py - Uses connection during experiments

## Connection Lifecycle Pattern

Always follow this pattern:

```python
camera = connect_camera()
if camera is None:
    print("Failed to connect")
    return

try:
    # ... do your work ...
    frame = grab_frame(camera)
    # ... more work ...
finally:
    disconnect_camera(camera)
```

The try/finally ensures cleanup happens even if an error occurs.

## Threading and Connections

Important if using multiple threads:
- Each camera connection should be used by only one thread
- If you need multiple threads accessing camera data, grab frames in one thread and pass them to others
- Never share the camera object between threads (unless using thread-safe wrappers, which this code doesn't have)

## Performance Notes

- Initial connection: ~100-300 ms (one-time cost)
- Disconnect: ~10-50 ms
- Not significant compared to frame grab time (2-50 ms per frame)

So it's fine to connect/disconnect for each quick task. For long-running monitoring, keep one connection open.
