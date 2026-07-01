# ESPI Plate Vibration — Whitman College

**A Python project for studying how violin and viola plates vibrate, built at Professor Hoffman's lab at Whitman College.**

This is an active research project. We are still adding things and fixing things as we go.


## What is this project actually about?

When you play a violin, the wooden top plate vibrates. Depending on the frequency of the note, different parts of the plate move — some parts swing back and forth a lot, others barely move at all. The spots that don't move are called nodes, and the full pattern is called a vibrational mode shape.

What's interesting is that vibrating plates actually behave very similarly to quantum systems. The same wave equations that describe how an electron moves in a box also describe how a plate vibrates. So studying a violin plate is genuinely useful for understanding physics beyond just acoustics.

The technique we use to see these patterns is called ESPI — Electronic Speckle Pattern Interferometry. Here is the short version of how it works:

1. You shine a laser on the plate. Laser light is special because all its waves are in sync — this creates a grainy texture on the surface called a speckle pattern.
2. You drive a speaker near the plate at a chosen frequency. The plate vibrates.
3. You take two photos. The parts that moved between the two photos look different. The parts that stayed still look the same.
4. You subtract the two photos. Where the plate moved, you get bright patches. Where it didn't move, you get black. The result is a fringe pattern — a picture of the vibration.

By stepping through many frequencies and saving a fringe image at each one, you build a full map of how the plate behaves across its acoustic range.

This project is replacing an older LabVIEW setup with open Python code that anyone can run, modify, and learn from.


## How the hardware is connected

Three devices work together:

1. **Signal generator** — sends an electrical signal to a speaker at the chosen frequency
2. **Speaker** — vibrates the plate without touching it
3. **Camera** — photographs the speckle pattern on the plate's surface

The software connects to both the signal generator and the camera, steps through a range of frequencies, and saves an image at each step.


## What the software does

The whole experiment is run by a single file: `run_experiment.py`

It asks you four questions:

* Which camera are you using?
* Which subtraction method do you want?
* What frequency range and camera settings do you want?
* Does everything look right? Start?

Then it opens a live camera preview so you can aim and focus. After that, you can adjust any settings as many times as you need — the program shows you the live feed again after each change so you can see the effect. When you are happy, you confirm and it runs the sweep.

After the sweep, the program opens an image viewer that shows your results one frequency at a time. Use the left and right arrow keys to move between images, and press Escape to close the viewer. A grid image with all frequencies is also saved to your output folder automatically.


## Two subtraction modes

| Mode | What it does | When to use it |
|---|---|---|
| Pair subtraction | Two frames are grabbed at each frequency and subtracted from each other | High-frequency vibration |
| Reference subtraction | One frame is captured with the plate at rest — every measurement frame is then compared to that baseline | Low-amplitude or slow vibration |


## Three supported cameras

| Camera | What you need to install |
|---|---|
| Basler (USB3) | `pip install pypylon` |
| Any USB webcam or ELP camera | `pip install opencv-python` (probably already installed) |
| Allied Vision (Vimba X) | Download vmbpy from the Allied Vision GitHub |

You only need one camera. The program detects which one you chose and handles everything else.


## Running the experiment

The full setup guide with Mac and Windows instructions and step-by-step verification is in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md). The short version is below.

**Step 1 — go into the code folder**

```
cd "ESPI Full Algorithm"
```

**Step 2 — create and activate a virtual environment**

Mac:
```
python3 -m venv venv_physics
source venv_physics/bin/activate
```

Windows:
```
python -m venv venv_physics
venv_physics\Scripts\activate
```

**Step 3 — install all packages**

```
pip install -r requirements.txt
```

**Step 4 — run the tests to confirm everything works**

```
python -m pytest tests/ -v
```

All 435 tests should pass. No hardware needed for this step.

**Step 5 — run the experiment**

```
python run_experiment.py
```

That's the only file you ever need to run. It will guide you through the rest.

If you have a Basler or Allied Vision camera, you also need to install their SDKs before running. See the full guide in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md).


## What is inside the project folder

```
Physics Research/
│
├── ESPI Full Algorithm/              ← all the working code lives here
│   │
│   ├── run_experiment.py             ← the one file you run to do an experiment
│   │
│   ├── complete_pipeline.py          ← sweep logic — Basler camera
│   ├── complete_pipeline_inclusive.py       ← sweep logic — any USB camera
│   ├── complete_pipeline_allied_vision.py   ← sweep logic — Allied Vision
│   │
│   ├── camera_control.py             ← camera functions — Basler
│   ├── camera_control_inclusive.py   ← camera functions — any USB camera
│   ├── camera_control_allied_vision.py  ← camera functions — Allied Vision
│   │
│   ├── signal_generator_control.py   ← talks to the Siglent signal generator
│   │
│   ├── capture_and_display.py        ← quick preview script — Basler
│   ├── capture_and_display_cv2.py    ← quick preview script — USB cameras
│   ├── capture_and_display_allied.py ← quick preview script — Allied Vision
│   │
│   ├── tests/                        ← automated tests (435 tests, no hardware needed)
│   │   ├── conftest.py
│   │   ├── test_camera_control.py
│   │   ├── test_camera_control_inclusive.py
│   │   ├── test_camera_control_allied_vision.py
│   │   ├── test_complete_pipeline.py
│   │   ├── test_complete_pipeline_inclusive.py
│   │   ├── test_complete_pipeline_allied_vision.py
│   │   ├── test_run_experiment.py
│   │   └── test_signal_generator_control.py
│   │
│   ├── README.md                     ← detailed guide for this folder
│   └── README_camera_control.md      ← guide for the camera library files
│
├── image_processing/                 ← standalone image subtraction demo
└── learn_testing/                    ← scratch space used while learning pytest
```

Everything useful is inside `ESPI Full Algorithm/`. The other folders are earlier experiments or learning exercises.


## Key files

**`run_experiment.py`**
The single entry point. Run this to do an experiment. It figures out which pipeline and camera library to use based on your answers. You never need to open the other files unless you want to understand or modify the internals.

**`complete_pipeline_*.py`**
There is one pipeline file per camera type. Each one handles connecting the camera and signal generator, showing the live preview, stepping through frequencies, grabbing and averaging frames, and saving images. They all return the same thing: a dictionary where the keys are frequencies in Hz and the values are images as NumPy arrays.

**`camera_control_*.py`**
Lower-level camera libraries. The pipeline files use these, but you can also call them directly in your own scripts if you want to do something custom. Full guide: [README_camera_control.md](ESPI%20Full%20Algorithm/README_camera_control.md)

**`signal_generator_control.py`**
Talks to the Siglent SDG signal generator over USB. Handles connecting, setting frequency and waveform, turning output on and off, and closing the connection cleanly.

**`tests/`**
435 automated tests covering every function in every file. None of them require a real camera or signal generator — all hardware is replaced with fakes during testing. To run them:

```bash
cd "ESPI Full Algorithm"
source venv_physics/bin/activate
python -m pytest tests/ -v
```


## Two subtraction methods in detail

**Pair subtraction**

At each frequency, two frames are grabbed back to back while the plate is already vibrating, then subtracted from each other. Their difference shows the speckle shift between two moments in time. This process repeats N times and all the differences are averaged together to reduce noise.

**Reference subtraction**

Before the signal generator is turned on, the camera captures one photo of the resting plate. That photo is saved as the reference. Then at each frequency, every measurement frame is subtracted from that same reference photo. The results are averaged. This method gives a consistent baseline across all frequencies because the reference never changes.


## What is still being worked on

The core pipeline works end to end for all three camera types. Things still in progress:

* **Node detection** — functions exist (`detect_nodes`, `has_nodes`) but the logic inside is not written yet
* **Analysis and classification** — using machine learning to automatically identify mode shapes is planned but not in the code yet


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

Standard library modules (`os`, `json`, `math`, `time`, `datetime`) come with Python — nothing to install.


Patrick Mulikuza
Professor Hoffman's Lab, Whitman College
