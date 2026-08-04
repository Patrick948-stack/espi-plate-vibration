# ESPI Full Algorithm/complete_pipeline.py - Complete ESPI Measurement Pipeline

## Purpose

This is the full ESPI (Electronic Speckle Pattern Interferometry) measurement workflow in one file. It orchestrates the entire process:

1. Connect to the camera and signal generator
2. Run a frequency sweep (e.g., 100 Hz to 500 Hz)
3. At each frequency, capture reference images
4. Capture measurement images
5. Process images to detect vibrations
6. Log results to disk
7. Display results

This is the "complete pipeline" that captures, processes, and analyzes data in one run.

## Overall Flow

The main workflow looks like this:

```
1. Initialize
   - Load configuration (camera settings, frequency range)
   - Connect to camera
   - Connect to signal generator
   
2. Loop through each frequency in the sweep
   - Set signal generator to this frequency
   - Wait for vibrations to stabilize
   - Capture reference images (no vibration)
   - Capture measurement images (with vibration)
   - Process images to find vibration patterns
   - Log results
   
3. Cleanup
   - Stop signal generator
   - Disconnect camera
   - Save summary report
   - Display results graph
```

## What the Pipeline Does at Each Frequency

At each frequency, the pipeline:

1. **Configure Signal Generator**
   - Set frequency (e.g., 100 Hz)
   - Set amplitude (e.g., 2.0 volts)
   - Turn output ON

2. **Wait for Stabilization**
   - Sleep for a moment (usually 0.5-1 second)
   - Lets vibrations reach steady state before measuring

3. **Capture Reference Images**
   - Grab several frames (typically 5-10)
   - Average them together
   - This is what the undisturbed sample looks like

4. **Capture Measurement Images**
   - Grab frames while vibration is active
   - Typically grab 30+ frames to average out speckle noise

5. **Process Images**
   - Subtract reference from each measurement
   - Amplify differences
   - Threshold to find vibrating regions
   - Detect nodes (areas of little vibration)
   - Measure peak vibration amplitude

6. **Log Results**
   - Save images to disk (reference, measurement, processed)
   - Save metadata (frequency, exposure, amplitude, peak vibration found)
   - Append to results CSV file

7. **Move to Next Frequency**
   - Turn off current signal
   - Increment frequency by step size
   - Repeat

## Key Data Structures

### Configuration Dictionary

Holds all experiment parameters:
```python
config = {
    "camera": {
        "exposure_us": 10000,      # 10 milliseconds
        "gain_db": 1.0,
        "pixel_format": "Mono8"
    },
    "experiment": {
        "start_frequency": 100,    # Hz
        "end_frequency": 500,      # Hz
        "frequency_step": 10,      # Hz increment
        "amplitude": 2.0,          # volts
        "stabilization_time": 1.0  # seconds
    },
    "processing": {
        "reference_frames": 10,     # frames to average for reference
        "measurement_frames": 30,   # frames to average for measurement
        "gain_factor": 10           # amplification for visualization
    }
}
```

### Results Dictionary

Stores measurement results for each frequency:
```python
results[frequency] = {
    "peak_vibration": 45.2,        # Maximum vibration amplitude (0-255)
    "vibrating_area_percent": 23.5, # Percentage of image that's vibrating
    "node_count": 3,               # Number of nodal regions found
    "exposure_us": 10000,          # Camera settings used
    "timestamp": "2025-07-22 14:30" # When measurement was taken
}
```

## Main Function

The main orchestration function does:

1. Parse configuration file (or use defaults)
2. Connect to camera and signal generator
3. For each frequency in the sweep:
   - Print progress
   - Configure and turn on signal generator
   - Wait for stabilization
   - Capture and process images
   - Log results
4. Turn off signal generator
5. Disconnect devices
6. Create results summary report
7. Display plot of peak vibration vs. frequency

## Key Helper Functions

### capture_and_average_frames(camera, num_frames)

Grabs multiple frames and averages them:
1. Grab num_frames from camera
2. Convert all to float arrays
3. Add them together
4. Divide by num_frames
5. Convert back to uint8
6. Return averaged frame

**Why average:** Reduces random speckle noise, gives cleaner vibration patterns.

### process_measurement_image(reference, measurement, gain_factor)

Processes a measurement frame:
1. Subtract reference from measurement
2. Amplify differences by gain_factor
3. Apply threshold to find vibrating areas
4. Return processed image

### detect_vibrating_regions(processed_image)

Analyzes processed image to find vibrating areas:
1. Find bright regions (areas that changed)
2. Filter by size (ignore noise, ignore huge uniform areas)
3. Calculate total vibrating area as percent of image
4. Return list of vibrating regions

### find_nodes(vibrating_regions)

Identifies node regions (minimal vibration):
1. Look for gaps between vibrating regions
2. Check for circular/modal patterns
3. Count distinct nodal points
4. Return node locations and count

## Typical Output Files

After running, you get:

```
experiments/
  2025-07-22_1430_espi_sweep/
    reference_100hz.png
    measurement_100hz.png
    processed_100hz.png
    reference_110hz.png
    measurement_110hz.png
    processed_110hz.png
    ... (one set for each frequency)
    
    results.csv
    results_summary.txt
    frequency_response.png (graph of peak vibration vs frequency)
```

### results.csv

```
frequency_hz,peak_vibration,vibrating_percent,node_count,timestamp
100,45.2,23.5,3,2025-07-22 14:30:15
110,52.1,28.3,3,2025-07-22 14:30:22
120,58.7,32.1,3,2025-07-22 14:30:29
...
```

### frequency_response.png

A plot showing:
- X-axis: Frequency (Hz)
- Y-axis: Peak vibration amplitude
- One point for each frequency
- Curve shows how the sample responds at different frequencies

## Error Handling

The pipeline handles:
- Camera disconnection mid-experiment
- Signal generator timeout
- Image processing errors
- File I/O problems

For each error, it logs the issue, tries to recover cleanly, and saves partial results.

## Typical Run Time

For a 100 Hz to 500 Hz sweep with 10 Hz steps (41 frequencies):
- At each frequency: ~3 seconds (stabilization + capture + processing)
- Total time: ~2-3 minutes

Can be adjusted by:
- Making frequency step larger (fewer steps)
- Reducing number of frames averaged
- Reducing stabilization time (not recommended, needs settling)

## Configuration and Customization

Most parameters can be changed in the config dictionary:
- Frequency range and step size
- Exposure and gain
- Number of frames to capture and average
- Amplification for visualization

Change these before starting the experiment, or pass them to main():

```python
main(
    start_freq=50,
    end_freq=1000,
    freq_step=5,
    amplitude=3.0,
    exposure_us=5000
)
```

## Recent Changes

**Amplitude/offset are now real parameters, and output actually turns on.**
`frequency_sweep()` and `reference_frequency_sweep()` used to hardcode
`amplitude=1.0, offset=0.0` inside their own `configure_channel()` call, with
no way to change either from outside the function. Both are now keyword
parameters (`amplitude=1.0, offset=0.0` as defaults, so no existing caller's
behavior changes), fed by `run_experiment_gui.py`'s new Signal Generator
controls via `run_experiment.run_pipeline()`.

Also added while touching this exact code: an explicit `turn_on_output(instr,
channel=1)` call right after `configure_channel(...)`. This file was still
importing `configure_channel()` from `signal_generator_control.py` at the
time (which already turns the output on internally, so this call was
harmless but redundant then) — it became the actual, sole way output gets
enabled once this file's import was migrated to `sdg_control` (see
"Related Files" below and `MIGRATION_PLAN.md`), whose own `configure_channel()`
deliberately does not turn output on itself. Matches what the "What the
Pipeline Does at Each Frequency" section above already described as the
intended behavior.

**The real Sweep now honors the Settings page's grayscale choice, not just Preview.**
`frequency_sweep()` and `reference_frequency_sweep()` used to always call
`connect_camera()` with no arguments, which connects in its default "standard"
Mono8 mode no matter what the user picked on the Settings page. Both now take
two new keyword parameters, `grayscale_method="standard"`,
`grayscale_color="R"` (matching `DEFAULT_SETTINGS`, so any existing caller
that omits them is unaffected), forward `grayscale_method` into
`connect_camera(grayscale_method=...)`, and run every captured frame
(including the reference frame in `reference_frequency_sweep()`) through
`_apply_grayscale_conversion()` (imported from `monitor_gui.py`, reused
rather than duplicated) before it is subtracted, applying the R/B channel
swap first whenever `format_info["needs_channel_swap"]` is set. A third
parameter, `grayscale_backend`, used to select between NumPy/Pillow/OpenCV
HSV single-channel extraction; it was removed along with the other two
backends, since NumPy slicing is now the only implementation.
`run_experiment.run_pipeline()` is the single place that reads these two
values from `settings_manager.load_settings()` and forwards them here, so
Preview and Sweep now always agree.

## Related Files

- camera_control.py - Camera capture and processing
- monitor_gui.py - Owns `_apply_grayscale_conversion()`, imported from here
  rather than duplicated, since Preview already proved it correct.
- sdg_control/ - Signal generator control package this file now imports
  from (waveform.py, output.py, limits.py, constants.py, status.py,
  connections.py, errors.py); see sdg_control.md. The older, single
  file `signal_generator_control.py` mentioned in "Recent Changes"
  above no longer exists in this project.
- live_graphs.py - Visualization during experiments
- run_experiment.py - Command-line version, and the single choke point
  that loads grayscale settings and forwards them into this file's
  sweep functions.
- run_experiment_gui.py - PyQt6 GUI version
