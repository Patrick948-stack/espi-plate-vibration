# ESPI Full Algorithm

This is the folder where all the actual working code lives. Everything in here is either a library you can import, or a script you can run directly.

If you want to run an experiment, there is only one file you need to know about: `run_experiment.py`.


## Running an experiment

```bash
source venv_physics/bin/activate
python run_experiment.py
```

The script walks you through four steps:

1. Pick your camera (Basler / USB webcam or ELP / Allied Vision)
2. Pick a subtraction mode (pair or reference)
3. Enter sweep parameters — start frequency, end frequency, step size, exposure, gain, output folder
4. Confirm your settings

After you confirm, a live camera preview opens so you can point and focus the camera at the plate. Press **`e`** to close the preview.

Then you get asked if you want to adjust any settings before the sweep starts. You can change the camera settings, the signal generator settings, or both. Each time you make a change, the live feed opens again so you can see the effect. You can adjust as many times as you need. When everything looks right, confirm and the sweep runs.

After the sweep, a viewer opens that shows your results one image at a time. Use the left and right arrow keys to move between frequencies. Press Escape to close. A grid image containing all frequencies is saved to your output folder at the same time.

**Exposure is always entered in seconds.** For example, `0.01` means 10 milliseconds. The program converts to the right internal unit per camera automatically.


## What is in this folder

| File | What it is | What it does |
|---|---|---|
| `run_experiment.py` | Script you run | Interactive entry point for all cameras and modes |
| `complete_pipeline.py` | Script or importable | Full frequency sweep — Basler camera |
| `complete_pipeline_inclusive.py` | Script or importable | Full frequency sweep — any USB/webcam camera |
| `complete_pipeline_allied_vision.py` | Script or importable | Full frequency sweep — Allied Vision camera |
| `camera_control.py` | Library | Low-level camera functions — Basler |
| `camera_control_inclusive.py` | Library | Low-level camera functions — USB/webcam |
| `camera_control_allied_vision.py` | Library | Low-level camera functions — Allied Vision |
| `signal_generator_control.py` | Library | Signal generator functions — Siglent SDG |
| `capture_and_display.py` | Script | Quick live preview only — Basler |
| `capture_and_display_cv2.py` | Script | Quick live preview only — any camera |
| `capture_and_display_allied.py` | Script | Quick live preview only — Allied Vision |


## The three pipelines compared

All three pipelines do the same job — step through a frequency range and save images. The differences are just which camera hardware they talk to.

| Feature | `complete_pipeline.py` | `complete_pipeline_inclusive.py` | `complete_pipeline_allied_vision.py` |
|---|---|---|---|
| Camera | Basler (pypylon) | Any USB/webcam (OpenCV) | Allied Vision (vmbpy) |
| Live preview before sweep | Yes — press `e` to start | Yes — press `e` to start | Yes — press `e` to start |
| Discard warmup frames | No | Yes | No |
| Auto-retry on failed grabs | No | Yes (up to 3 retries) | No |
| Saves JSON metadata | No | Yes | Yes |
| Exposure unit (internal) | Microseconds | OpenCV log₂ scale | Microseconds |
| Subtraction modes available | Pair and Reference | Pair and Reference | Pair and Reference |

If you are not sure which one to use, `complete_pipeline_inclusive.py` works with the widest range of hardware.


## The two subtraction modes

**Mode 1 — Pair subtraction**

Two frames are grabbed back to back at each frequency while the plate is already vibrating, then subtracted from each other.

At each frequency the program grabs Frame A and Frame B, subtracts one from the other to get a difference image, and repeats that process `n_averages` times. All the difference images are averaged together to reduce noise.

Good for high-frequency vibration where the plate moves a lot between frames.

**Mode 2 — Reference subtraction**

One photo of the resting plate is taken before the signal generator turns on. Then at each frequency, every measurement frame is compared against that same resting-state photo.

Before the sweep starts, the program captures one reference frame with the plate at rest. Then at each frequency it captures a measurement frame and subtracts the reference from it. This repeats `n_averages` times and all the results are averaged.

Good for low-amplitude vibration or when you want a consistent baseline across all frequencies.

The reference is captured after the exposure and gain are locked, so lighting conditions match exactly.


## Calling a pipeline from your own script

If you want to use the pipelines directly without the interactive prompts, you can import them:

```python
# Basler
from complete_pipeline import frequency_sweep

results = frequency_sweep(
    start_freq  = 100,
    end_freq    = 1000,
    step        = 100,
    n_averages  = 5,
    exposure_us = 10_000,    # microseconds (10 ms)
    gain        = 0.0,
    output_dir  = "output",
)
```

```python
# Any USB camera
from complete_pipeline_inclusive import frequency_sweep_inclusive

results = frequency_sweep_inclusive(
    start_freq = 100,
    end_freq   = 1000,
    step       = 100,
    n_averages = 5,
    exposure   = -6,         # OpenCV log₂ scale (-6 is roughly 15 ms)
    gain       = 0.0,
    output_dir = "output",
)
```

```python
# Allied Vision
from complete_pipeline_allied_vision import frequency_sweep_allied_vision

results = frequency_sweep_allied_vision(
    start_freq  = 100,
    end_freq    = 1000,
    step        = 100,
    n_averages  = 5,
    exposure_us = 10_000,    # microseconds
    gain        = 0.0,
    output_dir  = "output",
)
```

`results` is always a dictionary: `{frequency_in_hz: image_as_numpy_array, ...}`

All three functions also accept a `skip_live_feed=True` argument if you want to skip the preview window when calling them from a script.


## The signal generator

`signal_generator_control.py` handles talking to a Siglent SDG signal generator over USB.

| Function | What it does |
|---|---|
| `open_connection()` | Finds and connects to the signal generator |
| `get_identity(instr)` | Returns the device name and serial number |
| `configure_channel(instr, waveform, frequency, amplitude, offset, channel)` | Sets everything and turns the output on |
| `set_frequency(instr, freq, channel, waveform)` | Changes frequency during a sweep |
| `turn_off_output(instr, channel)` | Turns the output off |
| `close_connection(instr)` | Closes the connection cleanly |

If you ask for a frequency outside the instrument's allowed range for a given waveform, the value gets clamped automatically and a warning is printed.


## Camera libraries

Full documentation for the camera libraries is in [README_camera_control.md](README_camera_control.md).

**Short version — Basler**

```python
from camera_control import *

camera = connect_camera()
show_live_feed_from_camera(camera)    # aim, then press 'e'
set_exposure_manual(camera, 10000)    # 10 ms in microseconds
set_gain_manual(camera, 0.0)
frames = grab_n_frames(camera, 2)
diff   = substract_frames(frames[0], frames[1])
save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=10000, step="espi_raw")
disconnect_camera(camera)
```

**Short version — USB camera**

```python
from camera_control_inclusive import *

camera = connect_camera(camera_index=0)
show_live_feed_from_camera(camera)    # aim, then press 'e'
discard_warmup_frames(camera, n=10)
set_exposure_manual(camera, -6)       # -6 ≈ 15 ms in OpenCV log₂ scale
set_gain_manual(camera, 0.0)
frames = grab_n_frames(camera, 2, max_retries=3)
diff   = substract_frames(frames[0], frames[1])
disconnect_camera(camera)
```

**Short version — Allied Vision**

```python
from camera_control_allied_vision import *

camera = connect_camera()
show_live_feed_from_camera(camera)    # aim, then press 'e'
set_exposure_manual(camera, 10000)    # 10 ms in microseconds
set_gain_manual(camera, 0.0)
frames = grab_n_frames(camera, 2)
diff   = substract_frames(frames[0], frames[1])
disconnect_camera(camera)
```

**Exposure unit quick reminder:**
* Basler and Allied Vision use **microseconds** (`10000` = 10 ms)
* USB/OpenCV cameras use **log₂ scale** (`-6` ≈ 15 ms)
* `run_experiment.py` always uses **seconds** and converts automatically


## Output files

After a sweep, the output folder will contain:

| File | What it is |
|---|---|
| `espi_raw_2026-06-10_00170.2Hz_010000us.png` | The averaged difference image at that frequency |
| `session_metadata.json` | All settings used for this experiment |
| `session_log.txt` | Camera info at capture time |
| `sweep_results_2026-06-10_143022.png` | Grid image of all frequencies, saved after the sweep |

Filenames use exactly as many decimal places as the frequency needs, and are zero-padded so they sort correctly in any file browser.


## Running the automated tests

There are 435 tests covering every function in every file. They all run without a real camera or signal generator — the hardware is replaced with fake objects during testing.

```bash
source venv_physics/bin/activate
python -m pytest tests/ -v
```

| Test file | What it tests |
|---|---|
| `conftest.py` | Shared setup — fake images, mock cameras, mock signal generator |
| `test_camera_control.py` | Basler camera library |
| `test_camera_control_inclusive.py` | USB/OpenCV camera library |
| `test_camera_control_allied_vision.py` | Allied Vision camera library |
| `test_complete_pipeline.py` | Basler sweep logic |
| `test_complete_pipeline_inclusive.py` | USB sweep logic |
| `test_complete_pipeline_allied_vision.py` | Allied Vision sweep logic |
| `test_run_experiment.py` | Interactive entry point, exposure conversion, preview feed, settings loop |
| `test_signal_generator_control.py` | Signal generator functions |


## Dependencies

```
numpy            pip install numpy
opencv-python    pip install opencv-python
pyvisa           pip install pyvisa
pyvisa-py        pip install pyvisa-py

pypylon          pip install pypylon           (Basler cameras only)
vmbpy            install from wheel            (Allied Vision cameras only)
                 https://github.com/alliedvision/VmbPy
```


Patrick Mulikuza
Professor Hoffman's Lab, Whitman College
