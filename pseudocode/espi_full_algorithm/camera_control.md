# ESPI Full Algorithm/camera_control.py - Basler Camera Control

## Purpose

This file provides a complete, self-contained interface to control a Basler camera. It handles everything from connecting to the camera, setting exposure and pixel formats, capturing frames, processing ESPI data, and logging results to disk.

This file is independent and can be used in any other project. It only requires pypylon, numpy, and opencv-python to be installed.

## File Organization

The file is divided into 8 sections:

1. Camera Connection: open and close the camera
2. Camera Settings: exposure, pixel format, camera info
3. Region of Interest: crop sensor to smaller area
4. Image Capture: grab frames as arrays
5. ESPI Image Processing: subtract, amplify, threshold frames
6. Node Detection: find vibrating areas in data
7. File Logging: save images and session data
8. Quick View: save and display images

## Section 1: Camera Connection

### connect_camera()

Finds and opens the first available Basler camera.

**What it does:**
1. Use pylon.TlFactory to scan for connected cameras (USB3, GigE, etc.)
2. Create the first camera device found
3. Wrap it in a pylon.InstantCamera object for high-level control
4. Open communication with the camera
5. Force pixel format to Mono8 (ensures consistent data format)
6. Print success message with camera model name
7. Return the camera object

**Returns:** camera object if successful, None if no camera found

**Usage:**
```
camera = connect_camera()
if camera is None:
    print("No camera found")
else:
    # do work
    disconnect_camera(camera)
```

### disconnect_camera(camera)

Safely closes the connection to the camera.

**What it does:**
1. Check if camera is actively grabbing frames
2. If yes, stop grabbing to free buffers
3. Close the communication session
4. Free all camera resources
5. Print disconnection message

**Why this matters:** If you skip this step, the camera can stay locked and refuse the next connection until power-cycled.

## Section 2: Camera Settings

### set_exposure_manual(camera, exposure_us)

Disables auto-exposure and locks the camera to a specific exposure time.

**What it does:**
1. Set ExposureAuto to "Off" (disable auto-exposure)
2. Clamp the requested value to hardware limits (min to max)
3. Set the ExposureTime to the requested microseconds
4. Read back the actual value accepted (may differ due to rounding)
5. Print the actual exposure time
6. Return the actual value

**Input:** exposure_us in microseconds (1 ms = 1,000 µs)

**Why manual exposure:** It keeps brightness stable between frames, which is essential for ESPI measurements.

### set_exposure_auto(camera)

Lets the camera continuously adjust exposure for mid-gray brightness.

**What it does:**
1. Set ExposureAuto to "Continuous"
2. Camera constantly monitors brightness and adjusts exposure

**Use case:** Useful during initial alignment when you want to see something on screen. Never use during measurements because changing brightness ruins comparisons between frames.

### set_gain_manual(camera, gain_db)

Sets the amplification level to a specific decibel value.

**What it does:**
1. Disable automatic gain adjustment
2. Clamp gain to hardware limits
3. Set Gain to the requested value in decibels
4. Return actual value accepted

**Gain in decibels:** Higher dB means more amplification (brightens dark images but adds noise)

### set_pixel_format(camera, format_string)

Changes how the camera encodes pixel data.

**What it does:**
1. Set the PixelFormat property to the requested format
2. Print confirmation with format name

**Common formats:**
- "Mono8": 8-bit grayscale (0-255), fast, good for ESPI
- "Mono12": 12-bit grayscale (0-4095), more detail, larger files
- "Mono12Packed": 12-bit packed format, saves space

### get_camera_info(camera)

Reads and prints detailed camera specifications.

**What it does:**
1. Print model name
2. Print serial number
3. Print vendor name
4. Print firmware version
5. Print current exposure setting
6. Print current gain setting
7. Print current pixel format
8. Print image width and height

**Use this to:** Verify that settings changes took effect.

## Section 3: Region of Interest (ROI)

### set_roi(camera, x, y, width, height)

Crops the camera sensor to capture only a smaller region.

**What it does:**
1. Validate that x, y, width, height fit within the sensor
2. Clamp values to valid ranges
3. Set OffsetX, OffsetY, Width, Height properties
4. Return the actual ROI values accepted

**Use case:** Speeds up frame capture by ignoring parts of the sensor you don't need.

### reset_roi(camera)

Resets the ROI to capture the full sensor.

**What it does:**
1. Set offset to (0, 0)
2. Set width and height to full sensor dimensions

## Section 4: Image Capture

### grab_single_frame(camera)

Captures one frame from the camera.

**What it does:**
1. Use camera.GrabOne() to capture a single frame
2. If successful, extract the frame data and convert to numpy array
3. Return the array as Mono8 (0-255) or Mono12 (0-4095) depending on format
4. If failed, print error and return None

**Returns:** numpy array of shape (height, width) containing pixel values

### grab_single_frame_color(camera)

Present only so this module's interface matches camera_control_inclusive.py and camera_control_allied_vision.py, which both added a function with this same name (see the note below). Basler cameras in this project are always configured as Mono8 or Mono12, so there is no color to preserve here in the first place. This function simply calls grab_single_frame(camera) and returns whatever it returns.

**A bug found and fixed in the other two camera modules, not this one:**

camera_control_inclusive.py's grab_single_frame() (used for USB/webcam cameras) and camera_control_allied_vision.py's grab_single_frame() (used for Allied Vision cameras) both reduce a color frame down to plain greyscale before returning it. That is correct for monitor.py, capture_and_display*.py, and run_experiment.py, which all expect a ready to use 2D array. It silently broke monitor_gui.py's single-channel Red/Green/Blue extraction feature though: by the time that code saw the frame, the color data was already gone, so choosing Red, Green, Blue, or any of the three extraction backends made no visible difference at all, no matter which was picked. Both modules gained a new grab_single_frame_color() function that skips that internal reduction and returns the real (H, W, 3) BGR data instead, and monitor_gui.py's MonitorWorker was switched to call that new function. grab_single_frame() itself was left completely unchanged in every module, so nothing else in the project was affected.

### grab_single_frame_color_with_retry(camera, max_retries=3, retry_delay_s=0.3, max_total_wait_s=None)

Present for interface consistency with camera_control_inclusive.py and camera_control_allied_vision.py, which both need real retry logic for cameras that occasionally drop the first frame over USB or GigE. Basler connects over a dedicated GenICam link rather than shared USB bandwidth, so this simply delegates to grab_single_frame_color() and ignores all three retry parameters. They are still accepted, not just max_retries, so MonitorWorker can call this function identically no matter which camera module is active.

**A second bug found and fixed in the other two camera modules, not this one:**

After switching MonitorWorker to grab_single_frame_color(), a real USB webcam failed immediately with "Failed to grab frame, check camera connection" on the very first grab, even though connect_camera() had just opened it successfully. Some USB webcams need a brief moment to warm up right after being opened, and a single unretried read() attempt can fail even on a camera that is perfectly fine a moment later. This project already had grab_single_frame_with_retry() in camera_control_inclusive.py and camera_control_allied_vision.py for exactly this reason, used by other callers like grab_n_frames(), but MonitorWorker had never been switched to use a retrying grab function, only the plain one. Both modules gained grab_single_frame_color_with_retry(), mirroring grab_single_frame_with_retry()'s retry loop while preserving color, and MonitorWorker now calls that instead.

**A third bug found and fixed, once real hardware data came back:** adding retries alone did not fix it. The student ran a tiny standalone diagnostic script (10 read() attempts, 0.3 seconds apart, no project code involved) directly against their webcam, which showed isOpened() is True, the first two read() attempts fail, and every attempt from the third one onward succeeds. The first version of grab_single_frame_color_with_retry() retried three times back to back with no pause at all, which finishes in well under a millisecond total, nowhere near the real wall-clock time that camera needed to warm up, so it still failed even with retries in place. Added an actual time.sleep(0.3) between failed attempts (not after the final one, since there is nothing left to wait for), in both camera_control_inclusive.py and camera_control_allied_vision.py. Simulated the exact fail, fail, succeed pattern from the real hardware afterward and confirmed it now takes about 0.6 seconds and returns a real frame, matching what the student's own camera needed.

**A fourth bug found and fixed, once a more realistic diagnostic ran:** even the sleep-based fix above still failed on the real webcam when the monitor actually started. The earlier diagnostic never touched exposure or gain before reading; the real app always does (set_exposure_manual(), then set_gain_manual(), then the read loop). A second diagnostic that mirrored that exact sequence showed the first successful read() did not arrive until about 3.4 seconds had passed, forcing manual exposure and gain appears to make the camera driver briefly restart its stream, a much longer stall than three attempts with a 0.3 second sleep (0.6 seconds total) can cover. The same diagnostic also caught the camera dropping frames again, briefly, well after that initial warm-up had already succeeded.

A fixed attempt count cannot reliably bridge a stall like this, since it has no way to know how long any one failed attempt itself takes to return, which varied a lot between the two diagnostics. grab_single_frame_color_with_retry() gained a new max_total_wait_s parameter: when set, the function keeps retrying based on real elapsed time (using time.monotonic()) instead of stopping once max_retries is reached. It defaults to None, which keeps the exact old count-only behavior for any caller that does not pass it. MonitorWorker is the only caller that opts in, with a default of 6.0 seconds (about 1.75x the measured 3.4 second stall, for margin), applied to every single frame grab during a live session, not only the first one after connecting, since drops were seen to happen again mid-session too. That default lives in monitor_gui.py as DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S and is also readable from MonitorWorker's settings dict (frame_grab_max_total_wait_s, frame_grab_retry_delay_s), so it can be tuned without another code change once tested against the real camera. The same parameter was mirrored into camera_control_allied_vision.py, and added as an accepted-but-ignored parameter to this module's stub above, for the same interface-consistency reason max_retries already was.

### grab_continuous(camera, num_frames)

Captures multiple frames in a loop.

**What it does:**
1. Start the grabbing stream (most efficient for multiple frames)
2. Loop num_frames times:
   - Grab one frame using RetrieveResult()
   - Convert to numpy array
   - Add to results list
3. Stop grabbing
4. Return list of arrays

**Use case:** Much faster than calling grab_single_frame multiple times.

### grab_and_average(camera, num_frames)

Captures multiple frames and averages them together.

**What it does:**
1. Grab num_frames frames
2. Convert all to float arrays (so averaging doesn't lose precision)
3. Add all arrays together
4. Divide by num_frames
5. Convert back to uint8 (0-255)
6. Return the averaged array

**Use case:** Reduces noise and speckle in measurements.

## Section 5: ESPI Image Processing

### subtract_background(reference, current_frame)

Subtracts a reference image from the current frame to highlight changes.

**What it does:**
1. Convert both images to float (to handle negative values)
2. Subtract reference from current: difference = current - reference
3. Clip values to -128 to 127 range
4. Convert back to int8 (signed, so negatives are represented)
5. Return the difference image

**Purpose:** Shows only the vibration, not the static background.

### apply_threshold(image, threshold_value)

Turns an image into pure black and white (binary).

**What it does:**
1. Pixels below threshold become 0 (black)
2. Pixels at or above threshold become 255 (white)
3. Return binary image

**Use case:** Emphasizes where vibration is happening vs. not happening.

### average_multiple_frames(frame_list)

Takes a list of frames and returns their average.

**What it does:**
1. Convert all frames to float
2. Stack them into a 3D array
3. Calculate mean along the frame dimension
4. Convert back to uint8
5. Return averaged frame

**Use case:** Reduce noise by averaging multiple measurements.

## Section 6: Node Detection

### detect_node_regions(difference_image)

Finds areas in the difference image that show vibration.

**What it does:**
1. Find bright areas in the difference image
2. Perform morphological operations (open, close) to clean up noise
3. Find contours (connected regions)
4. Filter by size (ignore tiny noise, ignore huge regions)
5. Return list of node regions

**Returns:** List of (x, y, width, height) rectangles for each vibrating region

## Section 7: File Logging

### save_frame_as_png(image, filename)

Saves a numpy array as a PNG image file.

**What it does:**
1. Convert numpy array to OpenCV format if needed
2. Write to disk using cv2.imwrite()
3. Print confirmation message

**Use case:** Archiving measurement data.

### save_measurement_log(filename, exposure_us, gain_db, reference_info, result_info)

Saves measurement metadata to a text file.

**What it does:**
1. Create a text file with timestamp
2. Write camera settings (exposure, gain)
3. Write reference image info
4. Write result measurements
5. Write timestamps and session details
6. Close file

**Use case:** Keep a record of how each measurement was taken.

## Section 8: Quick View

### quick_view_image(image, title)

Displays an image in a window and waits for a key press.

**What it does:**
1. Convert image to displayable format
2. Open a window with the image
3. Wait for user to press any key
4. Close the window

**Use case:** Quick debugging during development.

### quick_view_and_save(image, filename, title)

Saves an image to disk AND displays it.

**What it does:**
1. Save the image as PNG
2. Display it in a window
3. Wait for key press
4. Close window

## Typical ESPI Workflow Using This File

1. Connect to camera: `camera = connect_camera()`
2. Configure camera: `set_exposure_manual(camera, 10000)` (10 ms)
3. Capture reference: `ref = grab_single_frame(camera)`
4. Capture measurements: `frames = grab_continuous(camera, 30)`
5. Process each frame: `diff = subtract_background(ref, frame)`
6. Amplify: `bright = cv2.convertScaleAbs(diff, alpha=gain_factor)`
7. Threshold: `binary = apply_threshold(bright, 128)`
8. Analyze: `nodes = detect_node_regions(binary)`
9. Log results: `save_measurement_log(...)`
10. Disconnect: `disconnect_camera(camera)`

## Key Concepts

### Pixel Values
- Mono8: 0-255 (8 bits)
- Mono12: 0-4095 (12 bits)

### Numpy Arrays
Images are stored as 2D numpy arrays where each element is a pixel value.
- Shape: (height, width)
- Indexing: array[y, x] gets pixel at row y, column x

### Exposure in Microseconds
- 1 millisecond = 1,000 microseconds
- 10 milliseconds = 10,000 microseconds
- Higher exposure = brighter image but slower frame rate

### Gain in Decibels
- 0 dB = no amplification
- 6 dB = doubles brightness
- 12 dB = quadruples brightness
- Use carefully to avoid noise

## Related Files

- camera_control_allied_vision.py - Same interface for Allied Vision cameras
- camera/connection.py - Lower-level connection code
- capture_and_display.py - GUI for real-time capture
- run_experiment.py - Frequency sweep experiments
