# ESPI Plate Vibration Analysis — Whitman College

**An open-source replacement for LabView to study how violin and viola plates vibrate.**

This project is being developed in Professor Hoffman's lab at Whitman College.
It is an ongoing, active research effort.

---

## The Research Question

Acoustical systems offer a rich experimental window into wave phenomena that parallel more abstract problems in quantum mechanics. Vibrating plates exhibit the same standing wave mathematics as two-dimensional quantum wells, and periodic tube resonators display band gap behavior analogous to solid-state systems. This research program at Whitman College, led by Professor Kurt Hoffman, develops low-cost experimental platforms to study these systems, with a particular focus on using Electronic Speckle Pattern Interferometry (ESPI) to map the vibrational normal modes of stringed instrument plates. In the ESPI technique, laser light scattered from a vibrating surface produces interference patterns that reveal regions of maximum and minimum displacement at a given driving frequency. By sweeping across a range of frequencies and capturing these fringe images non-invasively, the lab characterizes how vibrational mode shapes evolve across the acoustic spectrum of viola and violin top plates, including how those modes shift as an instrument undergoes successive stages of fabrication.

A parallel objective of the program is to develop the measurement infrastructure itself as a pedagogically shareable resource for undergraduate physics education. This has required transitioning the data acquisition and control system from proprietary LabVIEW software to an open, Python-based pipeline that encompasses camera control, signal generator synchronization, image subtraction, and automated frequency sweeping, making the experimental workflow reproducible, extensible, and accessible to non-specialists. Complementary work in the lab has addressed acoustic impedance measurements in periodic tube resonators, harmonic analysis of compound strings, and finite element modeling in COMSOL, together forming a suite of advanced laboratory experiments grounded in the shared mathematics of wave mechanics. Machine learning classifiers have also been applied to automate the identification of nodal regions in ESPI images, pointing toward a future where large-scale modal datasets can be analyzed without manual inspection.

---

## How the Experiment Works

The setup has three main pieces of hardware working together:

1. **A signal generator** drives a speaker at a chosen frequency. The speaker
   vibrates the plate without touching it.

2. **A laser** shines on the plate's surface. Because of a property of coherent
   light called interference, the reflected light forms a grainy texture (speckle)
   that shifts slightly wherever the surface moves.

3. **A Basler camera** captures that speckle pattern. The system takes two frames —
   one before excitation and one during — and subtracts them. Where the surface
   moved, the subtraction produces bright regions. Where it stayed still (nodes),
   it produces dark regions. The result is a **fringe pattern**: a visual map of
   how the plate is vibrating at that exact frequency.

This technique is called **ESPI** — Electronic Speckle Pattern Interferometry.

By sweeping through a range of frequencies and saving an ESPI image at each step,
the lab builds up a full picture of the plate's vibrational behavior.

---

## What This Software Does

LabView is the commercial software currently used to coordinate the hardware and
capture images. This project is building an open-source Python replacement that
does the same job, and eventually more.

The Python system:

- Connects to the signal generator and sets its frequency, waveform, and amplitude
- Connects to the Basler camera and controls exposure time and gain
- Runs a full frequency sweep automatically — stepping from a start frequency to
  an end frequency, capturing and saving ESPI images at each step
- Returns the images as data you can immediately analyze in Python

Downstream analysis (not yet in this codebase) includes Python modeling,
COMSOL finite element simulations, and machine learning classifiers that try to
connect vibrational patterns to measurable instrument quality.

---

## Hardware Requirements

| Device                       | Details                                                           |
| ---------------------------- | ----------------------------------------------------------------- |
| Basler camera                | USB3 Vision compatible — must be on a USB 3.0 port (the blue one) |
| Siglent SDG signal generator | SDG1000 series, connected via USB                                 |
| Speaker / excitation source  | Driven by the signal generator output                             |

---

## Getting Started

### 1. Create a virtual environment

```bash
cd "Physics Research"
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install pypylon numpy opencv-python pyvisa pyvisa-py
```

### 3. Run a frequency sweep

Edit `signal_generator_project/test_complete_pypeline.py` with your parameters,
then run it:

```bash
cd signal_generator_project
python3 test_complete_pypeline.py
```

A minimal example:

```python
from complete_pipeline import frequency_sweep

results = frequency_sweep(
    start_freq  = 100,       # Hz — first frequency to test
    end_freq    = 1000,      # Hz — last frequency to test
    step        = 100,       # Hz — increment between measurements
    n_averages  = 5,         # frame pairs averaged per frequency (more = less noise)
    exposure_us = 10000,     # camera exposure in microseconds (10 ms)
    gain        = 0.0,       # camera gain in dB (start at 0, increase if too dark)
    output_dir  = "/Users/yourname/Desktop/sweep_output",
)
```

Images are saved to `output_dir` as PNG files, named automatically with the
frequency, date, and exposure time so they sort correctly in any file browser.

---

## Project Structure

```
Physics Research/
│
├── signal_generator_project/      ← THE MAIN CODE — start here
│   ├── complete_pipeline.py       ← runs a full frequency sweep end-to-end
│   ├── camera_control.py          ← all camera functions (connect, capture, process)
│   ├── control_signal_generator.py← all signal generator functions
│   ├── test_complete_pypeline.py  ← example script to run a sweep
│   ├── README_camera_control.md   ← detailed guide for camera_control.py
│   └── examples/
│       └── basic_usage.py
│
├── camera/                        ← earlier modular version of the camera code
│   ├── connection.py              ← camera connect/disconnect
│   ├── capture.py                 ← frame grabbing
│   ├── settings.py                ← exposure, gain, pixel format
│   ├── roi.py                     ← region of interest
│   └── processing/
│       ├── substraction.py        ← frame subtraction
│       └── node_detection.py      ← node finding (in progress)
│
├── signal_generator/              ← earlier version of signal generator code
│   ├── control_signal_generator.py
│   ├── fcts_siglent.py
│   └── find_instruments.py
│
├── image_processing/              ← LEARNING FILES — not part of the system
│   └── learn_openCV/              ← experiments while learning OpenCV and pypylon
│
└── venv/                          ← Python virtual environment (not committed)
```

**The folder to work in is `signal_generator_project/`.** Everything else is
either an earlier iteration or files used while learning the libraries.

---

## Key Files Explained

### `complete_pipeline.py`

The top-level script. Call `frequency_sweep()` from here to run a full experiment.
It handles connecting both devices, stepping through frequencies, capturing and
averaging frames, and saving results — then disconnects everything cleanly when done.

### `camera_control.py`

A self-contained library for the Basler camera. Has its own detailed README:
[README_camera_control.md](signal_generator_project/README_camera_control.md).

### `control_signal_generator.py`

A self-contained library for the Siglent signal generator. Handles connecting via
USB, setting frequency/amplitude/waveform, turning output on and off, and
disconnecting safely.

---

## Project Status

This is an active, ongoing project. The core measurement loop — connect, sweep,
save — is working. The following areas are still in development:

- **Node detection** (`detect_nodes`, `has_nodes` in `camera_control.py`) —
  the function stubs are written but the logic is not yet implemented
- **Downstream analysis** — ML classifiers and COMSOL integration are planned
  but not yet part of this codebase

---

## Dependencies

```
pypylon        pip install pypylon
numpy          pip install numpy
opencv-python  pip install opencv-python
pyvisa         pip install pyvisa
pyvisa-py      pip install pyvisa-py
```

`os` and `datetime` are part of Python's standard library — no install needed.

---

_Whitman College — Professor Hoffman's Lab_
_Developed by Patrick Mulikuza_
