# ESPI Full Algorithm

This is the folder where all the actual working code lives. Everything in here is either a library you can import, or a script you can run directly.

If you want to run an experiment, there is only one file you need to know about: `run_experiment.py`.


## Getting started — Mac and Windows setup

Follow these stages in order. Each one has a quick check so you know it worked before moving to the next.


### Stage 1 — Make sure Python is installed

**Mac**

Open Terminal and run:

```
python3 --version
```

You should see something like `Python 3.10.x` or newer. If you get "command not found," download Python from python.org.

**Windows**

Open Command Prompt (search for `cmd` in the Start menu) and run:

```
python --version
```

You should see `Python 3.10.x` or newer. If you get an error, download Python from python.org. During the install, check the box that says **"Add Python to PATH"** — if you miss that, nothing will work from the terminal.


### Stage 2 — Get the code

If you are cloning for the first time:

```
git clone https://github.com/Patrick948-stack/espi-plate-vibration.git
```

If you already cloned it before and want the latest changes:

```
git pull
```

Check: you should see the `ESPI Full Algorithm` folder on your computer.


### Stage 3 — Open a terminal inside the right folder

You need to be inside the `ESPI Full Algorithm` folder for all the commands below to work.

**Mac**

```
cd "ESPI Full Algorithm"
```

**Windows — option A (from Command Prompt)**

```
cd "ESPI Full Algorithm"
```

**Windows — option B (faster)**

In File Explorer, open the `ESPI Full Algorithm` folder. Click the address bar at the top, type `cmd`, and press Enter. A terminal opens already inside that folder.

Check: run `ls` (Mac) or `dir` (Windows) and you should see files like `run_experiment.py` and `requirements.txt`.


### Stage 4 — Create a virtual environment

A virtual environment is a private Python space just for this project. It keeps the packages you install here separate from everything else on your computer.

**Mac**

```
python3 -m venv venv_physics
```

**Windows**

```
python -m venv venv_physics
```

Check: a folder called `venv_physics` should now appear inside `ESPI Full Algorithm`.


### Stage 5 — Activate the virtual environment

This is the step where Mac and Windows look the most different.

**Mac**

```
source venv_physics/bin/activate
```

**Windows**

```
venv_physics\Scripts\activate
```

Check: the beginning of your terminal line should now show `(venv_physics)`. If you don't see that, the environment is not active and the next steps will not work.

You need to activate the environment every time you open a new terminal window.


### Stage 6 — Install the Python packages

With the environment active, run:

```
pip install -r requirements.txt
```

This reads the `requirements.txt` file and installs everything the project needs: numpy, opencv, pyvisa, matplotlib, and pytest.

Check: run this to confirm all packages loaded correctly:

```
python -c "import numpy; import cv2; import pyvisa; import matplotlib; print('All packages installed correctly')"
```

If you see `All packages installed correctly`, you are good. If you see an error naming a specific package, that package did not install — re-run `pip install -r requirements.txt` and look for any error messages.


### Stage 7 — Run the automated tests

This is the most important check. There are 435 tests that verify every function in the project works correctly. They run without any hardware — no camera or signal generator needed.

```
python -m pytest tests/ -v
```

Check: the last line should say `435 passed`. If any tests fail, the error message will tell you exactly which function broke and why.

If all 435 pass, the code is working correctly on your machine and you are ready to run real experiments.


### Stage 8 — Camera-specific setup (only if you have one of these cameras)

The USB webcam or ELP camera works immediately with no extra steps — it uses opencv which is already installed. `capture_and_display_cv2.py` automatically picks the right OpenCV camera backend for your OS (DirectShow on Windows, AVFoundation on Mac) so this works the same way on either — an earlier version of this file hardcoded the Mac-only backend, which would have made this camera fail to open on Windows.

**Basler camera**

First, download and install the **Pylon Camera Software Suite** from the Basler website (basler.com). This gives your computer the drivers it needs to talk to the camera. Then, with `venv_physics` active, run:

```
pip install pypylon
```

Check:

```
python -c "from pypylon import pylon; print('Basler ready')"
```

If you see `Basler ready`, the Basler setup is complete.

**Allied Vision camera**

First, download and install **Vimba X** from the Allied Vision website. After installing, look inside the Vimba X installation folder for a file ending in `.whl` — that is the Python package. Then, with `venv_physics` active, run:

**Mac**

```
pip install /path/to/vmbpy_file.whl
```

**Windows**

```
pip install C:\path\to\vmbpy_file.whl
```

Check:

```
python -c "import vmbpy; print('Allied Vision ready')"
```

If you see `Allied Vision ready`, the Allied Vision setup is complete.


### Stage 8.5 — Signal generator setup (Windows only)

Mac and Linux can skip this stage — the signal generator works immediately once `pyvisa` and `pyvisa-py` are installed.

Windows needs one extra one-time step. This project talks to the signal generator through `pyvisa-py`, a lightweight backend that needs direct access to the USB device. Windows blocks that kind of direct access by default until a compatible driver is bound to the instrument — Mac and Linux allow it out of the box, which is why this step is Windows-only.

`requirements.txt` already installs the native USB library `pyusb` needs (`libusb-package`) automatically on Windows only — Stage 6's `pip install -r requirements.txt` handles it, nothing extra to run. The one step that genuinely cannot be done through pip is binding a working driver to the instrument, since that's an operating-system-level USB permission, not a Python package. Pick one of the two options below for that.

**Option A — Zadig (recommended: free, ~5 MB, no reboot)**

1. Download Zadig from [zadig.akeo.ie](https://zadig.akeo.ie) — a single small executable, no installer needed.
2. Plug in the signal generator and power it on.
3. Open Zadig, click **Options > List All Devices**.
4. In the dropdown, find the signal generator. It may show up under its model name, as **USB Test and Measurement Device**, or as **Unknown Device**. Some instruments list more than one entry (e.g. a separate control interface) — if the first one doesn't work, repeat this step for the others.
5. Make sure **WinUSB** is selected as the target driver, then click **Replace Driver** (it may say **Install Driver**).
6. Wait for it to finish, then close Zadig. No reboot needed.

Check, one layer at a time — with `venv_physics` active:

```
python -c "import usb.core; print(list(usb.core.find(find_all=True)))"
```

This talks to the USB driver layer directly, without `pyvisa` in the way. An empty list `[]` or a `NoBackendError` here means either `libusb-package` did not install (re-run `pip install -r requirements.txt` and check for errors) or the Zadig driver step above still needs fixing — go back and recheck those before moving on.

Once that prints the device, confirm `pyvisa` sees it too:

```
python -c "import pyvisa; rm = pyvisa.ResourceManager('@py'); print(rm.list_resources())"
```

The signal generator's address (something like `USB0::...::INSTR`) should appear in the printed list. You can also run `python test_signal_generator_only.py` for a full step-by-step connection test with clearer diagnostics at each stage.

**Option B — NI-VISA (heavier, official vendor runtime)**

Download and install the free **NI-VISA** runtime from National Instruments (ni.com). It installs its own driver and its own VISA backend. Once installed, `pyvisa.ResourceManager()` detects and uses it automatically instead of `pyvisa-py` — no code changes needed.

Zadig is the better default for this project: it's a tiny download with no installer, and it keeps the signal generator working through the same free `pyvisa-py` backend already used on Mac and Linux. NI-VISA is a much larger install and is only worth it if it's already needed for other instruments.


### Stage 9 — Run the experiment

With `venv_physics` active and all checks passing:

```
python run_experiment.py
```

The program will ask you which camera, which mode, and what settings you want. It then opens a live feed so you can aim the camera, runs the sweep, and shows you the results one image at a time.


## Running an experiment (quick reference for returning users)

Once set up, the only commands you need each time are:

**Mac**

```
source venv_physics/bin/activate
python run_experiment.py
```

**Windows**

```
venv_physics\Scripts\activate
python run_experiment.py
```

The program walks you through the rest.

After the sweep, a viewer opens showing your results one frequency at a time. Use the left and right arrow keys to move between images. Press Escape to close. A grid image with all frequencies is saved to your output folder automatically.

**Exposure is always entered in seconds.** For example, `0.01` means 10 milliseconds. The program converts to the right internal unit per camera automatically.


## Monitoring a camera before an experiment

If you just want to check focus, alignment, or brightness without running a full frequency sweep, use `monitor.py` instead of `run_experiment.py`:

```
python monitor.py
```

It asks which camera you want to monitor (Basler, USB/webcam, or Allied Vision), the camera index if that camera type supports more than one device, the exposure time in seconds, the gain in dB, a `gain_factor`, and an optional live graph. `gain_factor` only brightens what you see in the "Frame Subtraction" window on screen, it does not change the raw camera data or the exposure/gain hardware settings.

Once you confirm, it opens the matching `capture_and_display*.py` script with two windows, plus a third if you asked for a graph:

- **Live Feed** — the raw frame straight from the camera
- **Frame Subtraction** — the absolute difference between each pair of consecutive frames, amplified by `gain_factor`
- **histogram / log_histogram / 3d** (optional) — a live graph of the raw frame's pixel intensity, see [Live pixel intensity graph](#live-pixel-intensity-graph) below

Press `q` inside any of the camera windows to close the monitor and return to the terminal. Basler only ever connects to the first camera pypylon finds (`camera_control.py` has no index parameter), so `monitor.py` skips the camera index question for that choice.

You can also call each `capture_and_display*.py` script's `main()` directly from your own code instead of going through `monitor.py`:

```python
import capture_and_display as cad
cad.main(exposure_us=10000, gain_db=1.0, gain_factor=20, graph_type="histogram")
```


## Live pixel intensity graph

`live_graphs.py` provides an optional third preview window: a live graph of the raw "Live Feed" frame's pixel intensity, as a histogram (linear or log scale) or a 3D surface. It grew out of two exploratory scripts, `Learning/graph.py` (3D surface of one saved image) and `Learning/graph2.py` (linear histogram of one saved image), plus a LabVIEW-style log-scale histogram function written directly for live use — this file rebuilds all three as fast, in-place-updating versions that work on frames straight out of the camera instead of a file on disk.

| Type | What it shows | Update rate |
|---|---|---|
| `histogram` | Bar chart, linear y-axis: how many pixels have each intensity value (0-255) | Every frame — `numpy.bincount` counts all pixels in one vectorized call, and only the 256 bar heights change per frame, nothing is rebuilt |
| `log_histogram` | Line plot, log y-axis, dark theme (matches LabVIEW's "Number of Pixels vs Pixel Value" plot) | Every frame — same `numpy.bincount` counting, only the line's y-data changes per frame |
| `3d` | 3D surface: X = column, Y = row, Z = intensity | A few times per second (throttled), not every frame |

`log_histogram` exists alongside the plain `histogram` because a linear y-axis is dominated by whichever intensity value has the most pixels (usually the background) — every rarer value gets squashed to an invisible sliver near the bottom. A log y-axis keeps rare values visible at the same time as the dominant peak.

The 3D option is intentionally throttled and heavily downsampled. matplotlib's 3D renderer (`mplot3d`) is a pure-Python, non-GPU-accelerated renderer that depth-sorts every quad in the surface on every redraw — there is no way to make a full 3D surface redraw at full camera frame rate (15-30+ fps) in matplotlib, downsampled or not. Neither histogram option has that ceiling since they only ever update 256 numbers.

Select a type through `monitor.py`'s "Graph type" question (`none`, `histogram`, `log_histogram`, or `3d`; `none` is the default, so nothing changes for anyone who doesn't ask for it), or pass `graph_type="histogram"` / `graph_type="log_histogram"` / `graph_type="3d"` directly to any `capture_and_display*.py` script's `main()`.


## What is in this folder

| File | What it is | What it does |
|---|---|---|
| `run_experiment.py` | Script you run | Interactive entry point for all cameras and modes |
| `monitor.py` | Script you run | Interactive live preview — pick a camera, set exposure/gain/gain_factor/graph type, watch Live Feed + Frame Subtraction (+ optional graph) |
| `live_graphs.py` | Library | Live histogram / 3D surface plot of pixel intensity, `create_live_graph(graph_type)` |
| `requirements.txt` | Package list | Install everything with `pip install -r requirements.txt` |
| `complete_pipeline.py` | Script or importable | Full frequency sweep — Basler camera |
| `complete_pipeline_inclusive.py` | Script or importable | Full frequency sweep — any USB/webcam camera |
| `complete_pipeline_allied_vision.py` | Script or importable | Full frequency sweep — Allied Vision camera |
| `camera_control.py` | Library | Low-level camera functions — Basler |
| `camera_control_inclusive.py` | Library | Low-level camera functions — USB/webcam |
| `camera_control_allied_vision.py` | Library | Low-level camera functions — Allied Vision |
| `signal_generator_control.py` | Library | Signal generator functions — Siglent SDG |
| `capture_and_display.py` | Script or importable | Live preview only — Basler. `main(exposure_us, gain_db, gain_factor, graph_type)` |
| `capture_and_display_cv2.py` | Script or importable | Live preview only — any camera. `main(camera_index, exposure, gain, gain_factor, graph_type)` |
| `capture_and_display_allied.py` | Script or importable | Live preview only — Allied Vision. `main(camera_index, exposure_us, gain, gain_factor, list_cameras, graph_type)` |


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

There are 562 tests covering every function in every file. They all run without a real camera or signal generator — the hardware is replaced with fake objects during testing.

**Mac**

```
source venv_physics/bin/activate
python -m pytest tests/ -v
```

**Windows**

```
venv_physics\Scripts\activate
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
| `test_monitor.py` | monitor.py entry point — camera choice, settings prompts, exposure conversion, error messages |
| `test_capture_and_display.py` | Basler live preview script |
| `test_capture_and_display_cv2.py` | USB/OpenCV live preview script |
| `test_capture_and_display_allied.py` | Allied Vision live preview script |
| `test_signal_generator_control.py` | Signal generator functions |


Patrick Mulikuza
Professor Hoffman's Lab, Whitman College
