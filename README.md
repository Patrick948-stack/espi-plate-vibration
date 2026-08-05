# ESPI Plate Vibration: Whitman College

**A Python project for studying how musical instrument soundboards and plates vibrate, built at Professor Hoffman's lab at Whitman College.**

This is an active research project. We are still adding things and fixing things as we go.

## What is this project actually about?

Electronic Speckle Pattern Interferometry (ESPI) is an ultra-precise, non-contact imaging technique used to measure microscopic movements, vibrations, or deformations in an object. By splitting a single laser beam into a reference path and an object path, a camera captures the unique, grainy "speckle pattern" reflected off a surface. When the object undergoes stress or vibration, the camera tracks how these speckles shift, generating a visual map of overlapping light waves that look like zebra stripes. Each stripe represents physical movement down to a fraction of a wavelength of light. This technique is invaluable because it allows engineers and researchers to see real-time, nanometer-scale structural changes across an entire surface simultaneously without physically touching or damaging the sample.

At Whitman College, Professor Kurt Hoffman’s research utilizes ESPI to study the complex physics of acoustics and musical instruments, specifically mapping how sound waves physically deform and vibrate stringed instruments like guitars. By tracking how a wooden plate's resonant behaviors evolve as its physical boundaries and shapes change, his lab provides instrument makers and acoustic engineers with precise, visual data to optimize instrument design and predict structural resonance.

Traditionally, conducting this cutting-edge research required tens of thousands of dollars in high-end optical equipment and costly proprietary software.

This open-source Python application directly supports Professor Hoffman’s goal of democratizing ESPI technology by eliminating the financial burden of restrictive software licensing, making advanced optical and acoustic research accessible to independent creators, luthiers, and undergraduate laboratories worldwide.

This project is replacing an older LabVIEW setup with open Python code that anyone can run, modify, and learn from.

## How the hardware is connected

Three devices work together:

1. **Signal generator**: sends an electrical signal to a speaker at the chosen frequency
2. **Speaker**: vibrates the plate without touching it
3. **Camera**: photographs the speckle pattern on the plate's surface

The software connects to both the signal generator and the camera, steps through a range of frequencies, and saves an image at each step.

## What the software does

The main way to run this software is through one app with a single main window. Run one command, `python -m espi_app.main`, and a landing page opens with two big buttons, **Monitor Mode** and **Scan Mode**, plus Settings and Help. The "Getting Started" section below walks you all the way from an empty computer to this window on screen, no programming experience assumed.

<p align="center">
  <img src="espi_app/screenshots/landing_page_light.png" width="49%" alt="espi_app landing page, light mode">
  <img src="espi_app/screenshots/landing_page_dark.png" width="49%" alt="espi_app landing page, dark mode">
</p>

**Scan Mode** runs a full frequency sweep experiment. Pick your camera and subtraction method, set your frequency range and camera settings, then preview the live camera feed so you can aim and focus. Adjust anything as many times as you need; the preview updates after every change so you can see the effect before committing. When you are happy, start the sweep. A real progress bar tracks it, and a Stop button ends it early without leaving the camera or signal generator in a bad state. When it finishes, a Results page shows your images one frequency at a time, with Previous and Next buttons and arrow key navigation. A grid image with all frequencies is also saved to your output folder automatically.

**Monitor Mode** just watches the live camera feed and frame subtraction, without running a full sweep: useful for checking focus, alignment, or brightness before you commit to a real experiment.

<p align="center">
  <img src="espi_app/screenshots/scan_mode_light.png" width="49%" alt="Scan Mode Setup page, light mode">
  <img src="espi_app/screenshots/monitor_mode_light.png" width="49%" alt="Monitor Mode Setup page, light mode">
</p>
<p align="center">
  <img src="ESPI%20Full%20Algorithm/screenshots/run_experiment_gui_sweep.png" width="49%" alt="Scan Mode Sweep page with a running sweep and Stop Sweep visible">
  <img src="ESPI%20Full%20Algorithm/screenshots/monitor_gui_live_monitor.png" width="49%" alt="Monitor Mode Live Monitor page showing Live Feed and Frame Subtraction">
</p>

Both modes are documented in full detail, with more screenshots (including the Settings dialog in both themes), in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md) and [espi_app/README.md](espi_app/README.md).

If you would rather type answers into a terminal than click through a window, `run_experiment.py` (a full sweep) and `monitor.py` (just the live preview) run the exact same underlying logic with typed questions instead of a GUI. Both live in `ESPI Full Algorithm/` and are covered in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md). Most people should start with the main window above instead.

## Three supported cameras

| Camera                       | What you need to install                                 |
| ---------------------------- | -------------------------------------------------------- |
| Basler (USB3)                | `pip install pypylon`                                    |
| Any USB webcam or ELP camera | `pip install opencv-python` (probably already installed) |
| Allied Vision (Vimba X)      | Download vmbpy from the Allied Vision GitHub             |

You only need one camera. The program detects which one you chose and handles everything else.

## Getting Started

This section walks you through everything, from an empty computer to the app's main window on screen. No programming experience is assumed. Follow the stages in order; each one has a check so you know it worked before moving on to the next.

### Before you start: what is "the terminal"?

Every stage below asks you to type a command into "the terminal." If you have never used one before, here is what that means and how to open it.

A terminal (also called a command line, command prompt, or shell) is a window where you type text commands instead of clicking buttons. It looks intimidating the first time, but every command in this guide is written out exactly as you should type it, so you never have to guess.

**On Mac:** press Cmd + Space to open Spotlight Search, type `Terminal`, and press Enter. Or open Finder, go to Applications, then Utilities, and double click Terminal.

**On Windows:** press the Windows key, type `cmd` for Command Prompt (or `PowerShell`), and press Enter. Windows 11 usually opens something called "Windows Terminal," which can run either Command Prompt or PowerShell inside it. Either one works for this guide; anywhere a command only works in one of them, this guide says so.

**If you install VS Code (Stage 1 below):** it comes with a terminal built in, already pointed at whatever folder you have open, so you do not need to open a separate terminal app at all. Keyboard shortcut: Ctrl + `` ` `` (the backtick key, usually just above Tab) on Windows, Cmd + `` ` `` on Mac. Or use the menu: **Terminal**, then **New Terminal**.

### Stage 1: Install a code editor (recommended, not required)

A code editor is not strictly necessary; every command below works from your computer's own terminal app too. But Visual Studio Code (VS Code) is free, beginner friendly, has a terminal built in, and makes it easy to browse and edit the project's files, so this guide assumes you have it.

1. Go to [code.visualstudio.com](https://code.visualstudio.com) and click the download button; it detects your operating system automatically.
2. Run the installer, keeping the default options.
3. Open VS Code once to confirm it launches.

### Stage 2: Install Python

**Mac**

Open Terminal and type this, then press Enter:

```
python3 --version
```

You should see something like `Python 3.10.x` or newer.

If something goes wrong: seeing `command not found: python3` means Python is not installed yet. Download it from [python.org](https://www.python.org/downloads/), run the installer, then completely close and reopen Terminal (a terminal sometimes only notices newly installed programs after it restarts) and try the command again.

**Windows**

Open Command Prompt (search for `cmd` in the Start menu) and type this, then press Enter:

```
python --version
```

You should see `Python 3.10.x` or newer.

If something goes wrong: seeing `'python' is not recognized as an internal or external command` means Python is either not installed, or it was installed without being added to your system's PATH (the list of places Windows looks for programs by name). Download Python from [python.org](https://www.python.org/downloads/), run the installer, and this time check the box that says **"Add Python to PATH"** before clicking Install. Then completely close and reopen your terminal and try again. If it still fails, restart your whole computer; Windows sometimes needs a full restart to notice PATH changes.

### Stage 3: Install Git

Git is the tool that downloads ("clones") this project's code onto your computer and keeps it up to date. If you would rather skip installing anything extra, you can download the code as a ZIP file instead; see Stage 4 below for that option, and skip this stage entirely.

**Mac**

Open Terminal and type:

```
git --version
```

On many Macs, typing this the very first time pops up a window offering to install Apple's "Command Line Developer Tools," which include Git. Click **Install**, wait for it to finish, then run `git --version` again to confirm.

If nothing pops up and you see `command not found: git`, download Git from [git-scm.com](https://git-scm.com), run the installer using the default options, then reopen Terminal and try again.

**Windows**

Download Git from [git-scm.com](https://git-scm.com), run the installer, and keep the default options throughout (it also installs something called "Git Bash," which you do not need to use; Command Prompt and PowerShell both still work fine for every command in this guide). Then open a fresh terminal and type:

```
git --version
```

You should see a version number.

If something goes wrong: seeing `'git' is not recognized` means the installer has not finished, or your terminal was open before you installed Git. Completely close and reopen your terminal and try again.

### Stage 4: Get the code

**Option A: clone it with Git**

Open a terminal anywhere you would like the project folder to end up (for example, your Desktop or Documents folder), and run:

```
git clone https://github.com/Patrick948-stack/espi-plate-vibration.git
```

If you are using VS Code, there is also a point-and-click way: press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows) to open the Command Palette, type `Git: Clone`, press Enter, and paste in `https://github.com/Patrick948-stack/espi-plate-vibration.git` when asked.

If you already have the code and just want the latest changes, run this from inside the project folder instead of cloning again:

```
git pull
```

**Option B: download it as a ZIP file, no Git needed**

Go to the project's page on GitHub, click the green **Code** button, then **Download ZIP**. Once it downloads, double click the ZIP file to unzip it (Windows may ask you to "Extract All" instead; either way works).

Check: either way, you should now have a folder on your computer containing, among other things, an `ESPI Full Algorithm` folder, an `espi_app` folder, and this `README.md` file.

### Stage 5: Open a terminal inside the project folder

Every command in the rest of this guide has to run while your terminal is "inside" this project's top folder (the one containing `ESPI Full Algorithm/`, `espi_app/`, and this file). If you run a command from the wrong folder, you will usually see an error like `No such file or directory` or `The system cannot find the file specified`; that almost always means you are in the wrong folder, not that something is actually broken.

**If you are using VS Code:** click **File**, then **Open Folder**, and choose the project folder. Then open the built in terminal (see "Before you start" above); it opens already pointed at the right place.

**If you are using your own terminal app:** use `cd` (which means "change directory," the terminal's word for "folder") followed by the path to wherever the folder ended up. For example, if you cloned it onto your Desktop:

Mac:

```
cd ~/Desktop/espi-plate-vibration
```

Windows:

```
cd %USERPROFILE%\Desktop\espi-plate-vibration
```

Check: type `ls` (Mac) or `dir` (Windows) and press Enter. You should see `README.md`, `requirements.txt`, `ESPI Full Algorithm`, and `espi_app` in the list.

### Stage 6: Create a virtual environment

A virtual environment is a private, self contained copy of Python just for this project. It keeps the packages this project needs separate from anything else installed on your computer, so nothing here interferes with other Python projects, and nothing else interferes with this one.

**Mac**

```
python3 -m venv venv_physics
```

**Windows**

```
python -m venv venv_physics
```

Check: a new folder called `venv_physics` should appear in the project folder. Confirm with `ls` (Mac) or `dir` (Windows).

If something goes wrong: this step rarely fails if Stage 2's check passed. If you see an error mentioning `ensurepip` or `venv`, reinstall Python from python.org using the full installer rather than a minimal one.

### Stage 7: Activate the virtual environment

"Activating" tells your terminal to use this project's private Python instead of your computer's main one. You have to do this every time you open a new terminal window to work on this project; it does not stay switched on permanently.

**Mac**

```
source venv_physics/bin/activate
```

**Windows, in Command Prompt**

```
venv_physics\Scripts\activate
```

**Windows, in PowerShell**

PowerShell blocks running scripts by default, for security reasons, so activation needs one extra line first:

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv_physics\Scripts\Activate.ps1
```

If something goes wrong: a red error mentioning that "running scripts is disabled on this system" is that same PowerShell security block. Run the `Set-ExecutionPolicy` line above first; it only affects the current terminal window, not your whole computer. If you would rather avoid PowerShell's script restrictions entirely, switch to Command Prompt instead.

Check: after activating, the very start of your terminal's input line should now show `(venv_physics)` before anything else you type. If you do not see that, activation did not work, and the next steps will use the wrong Python; try again.

### Stage 8: Install the Python packages

With the environment active (you should see `(venv_physics)` at the start of your terminal line), run both of these, one at a time:

```
pip install -r requirements.txt
pip install -r "ESPI Full Algorithm/requirements.txt"
```

Two separate installs are needed because there are two `requirements.txt` files: the first is for the main app window itself (`espi_app`), and the second is for everything Monitor Mode and Scan Mode actually need under the hood (camera libraries, matplotlib, and so on), since the main window opens that code directly the moment you click a mode button. This step needs an internet connection and can take a few minutes the first time; that is normal, let it finish.

If something goes wrong: seeing `'pip' is not recognized` or `command not found: pip` almost always means your virtual environment is not active; go back to Stage 7. A network or SSL related error usually means an internet or firewall problem; if you are on a school or work network, try a different one if you have access to one, since some of those networks block package installs.

### Stage 9: Run the automated tests

This is the most important check in the whole setup. There are over a thousand automated tests that verify the project works correctly, and they all run without needing any camera or signal generator plugged in.

```
python -m pytest tests espi_app/tests "ESPI Full Algorithm/tests" -v
```

A long list of lines will scroll by; that is normal, it is one line per test. Check the very last line of the output; it should say something like `1100 passed, 21 skipped`.

If something goes wrong: if the last line mentions any failures, scroll up; pytest prints exactly which test failed and why, right above that summary line. If every single test fails immediately with an import error, your virtual environment is probably not active, or Stage 8 did not finish successfully; go back and check both of those first. If the test run seems to hang for more than a minute or two without finishing, see the "Common Issues" section in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md) for a known, harmless cause and a workaround. Skipped tests are normal too; they mark checks that only apply to a camera type or platform you do not have.

### Stage 10: Launch the app

With `venv_physics` still active, run:

```
python -m espi_app.main
```

A window titled "ESPI Camera Control" should open: the ESPI logo, a title, and two large cards, Monitor Mode and Scan Mode, plus Settings and Help buttons at the bottom. Nothing else needs to be running first; no camera or signal generator has to be plugged in just to see this window. Click Monitor Mode or Scan Mode to open that dashboard.

If you have a Basler or Allied Vision camera, one more one-time step is needed before that specific camera will connect: installing its manufacturer's software. A plain USB webcam or ELP camera needs no extra steps at all. See "Camera specific setup" in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md) for both cameras' install steps.

### Running the app again later

Once everything above is set up, the only commands you need each time you come back are, from inside the project folder:

**Mac**

```
source venv_physics/bin/activate
python -m espi_app.main
```

**Windows**

```
venv_physics\Scripts\activate
python -m espi_app.main
```

## What is inside the project folder

```
Physics Research/
│
├── espi_app/                          ← the main window: python -m espi_app.main
│   ├── main.py                        ← entry point
│   ├── main_window.py                 ← LandingPage, launches Monitor/Scan dashboards
│   ├── settings.py                    ← SettingsManager (~/.espi_app/settings.json)
│   ├── settings_dialog.py             ← Settings window
│   ├── styles.py                      ← light/dark theme stylesheets
│   ├── tests/                         ← pytest-qt regression tests
│   └── README.md                      ← guide for this folder
│
├── ESPI Full Algorithm/              ← all the camera, signal generator, and sweep logic lives here
│   │
│   ├── monitor_gui.py                ← Monitor Mode's window (espi_app opens this)
│   ├── run_experiment_gui.py         ← Scan Mode's window (espi_app opens this)
│   │
│   ├── run_experiment.py             ← terminal-only version of a full sweep, typed questions instead of a GUI
│   ├── monitor.py                    ← terminal-only version of the live preview
│   │
│   ├── complete_pipeline.py          ← sweep logic: Basler camera
│   ├── complete_pipeline_inclusive.py       ← sweep logic: any USB camera
│   ├── complete_pipeline_allied_vision.py   ← sweep logic: Allied Vision
│   │
│   ├── camera_control.py             ← camera functions: Basler
│   ├── camera_control_inclusive.py   ← camera functions: any USB camera
│   ├── camera_control_allied_vision.py  ← camera functions: Allied Vision
│   │
│   ├── sdg_control/                  ← talks to the Siglent signal generator (modular package)
│   │
│   ├── capture_and_display.py        ← quick preview script: Basler
│   ├── capture_and_display_cv2.py    ← quick preview script: USB cameras
│   ├── capture_and_display_allied.py ← quick preview script: Allied Vision
│   │
│   ├── tests/                        ← automated tests, no hardware needed
│   └── README.md                     ← detailed guide for this folder
│
├── tests/                             ← automated tests for the two dashboards' shared settings/behavior
├── pseudocode/                        ← plain English walkthrough of every file above, for learning without reading raw code
├── requirements.txt                   ← packages espi_app itself needs: pip install -r requirements.txt
└── README.md                          ← this file
```

The main app (`espi_app/`) is what most people should run. `ESPI Full Algorithm/` holds every camera, signal generator, and sweep logic file it opens under the hood, plus the terminal-only scripts and a much more detailed README for anyone who wants to go deeper into that code specifically.

## Key files

**`espi_app/main.py`**
The main entry point. Run `python -m espi_app.main` from the project root to open the landing page window described above.

**`ESPI Full Algorithm/run_experiment_gui.py` and `monitor_gui.py`**
The two dashboards the landing page opens: Scan Mode and Monitor Mode. You can also run either one directly, without going through the landing page, with `python run_experiment_gui.py` or `python monitor_gui.py` from inside `ESPI Full Algorithm/`.

**`ESPI Full Algorithm/run_experiment.py` and `monitor.py`**
Terminal-only versions of the same two things, for anyone who prefers typed questions over a window, or wants to script an experiment without a GUI at all.

**`complete_pipeline_*.py`**
There is one pipeline file per camera type. Each one handles connecting the camera and signal generator, showing the live preview, stepping through frequencies, grabbing and averaging frames, and saving images. They all return the same thing: a dictionary where the keys are frequencies in Hz and the values are images as NumPy arrays.

**`camera_control_*.py`**
Lower-level camera libraries. The pipeline files use these, but you can also call them directly in your own scripts if you want to do something custom.

**`sdg_control/`**
Talks to the Siglent SDG signal generator over USB. Handles connecting, setting frequency and waveform, turning output on and off, and closing the connection cleanly. A modular package (`connections.py`, `status.py`, `output.py`, `waveform.py`, `limits.py`, `constants.py`, `errors.py`): see [sdg_control/README.md](ESPI%20Full%20Algorithm/sdg_control/README.md).

**`tests/`, `espi_app/tests/`, and `ESPI Full Algorithm/tests/`**
Over a thousand automated tests covering every function in every file, across all three test folders. None of them require a real camera or signal generator: all hardware is replaced with fakes during testing. To run every one of them:

```bash
source venv_physics/bin/activate
python -m pytest tests espi_app/tests "ESPI Full Algorithm/tests" -v
```

## What is still being worked on

The core pipeline works end to end for all three camera types. Things still in progress:

- **Node detection**: functions exist (`detect_nodes`, `has_nodes`) but the logic inside is not written yet
- **Analysis and classification**: using machine learning to automatically identify mode shapes is planned but not in the code yet

## Dependencies

```
matplotlib       pip install matplotlib
numpy            pip install numpy
opencv-python    pip install opencv-python
PyQt6            pip install PyQt6
pyvisa           pip install pyvisa
pyvisa-py        pip install pyvisa-py
qtawesome        pip install qtawesome
pytest           pip install pytest            (for running the automated tests)
pytest-qt        pip install pytest-qt         (for running the automated tests)

pypylon          pip install pypylon           (Basler cameras only)
vmbpy            install from wheel            (Allied Vision cameras only)
                 https://github.com/alliedvision/VmbPy
```

`pip install -r requirements.txt` and `pip install -r "ESPI Full Algorithm/requirements.txt"` (Stage 8 above) install everything except `vmbpy`, which is not published on the normal Python package index; see "Camera specific setup" in [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md) if you have an Allied Vision camera.

Standard library modules (`os`, `json`, `math`, `time`, `datetime`) come with Python: nothing to install.

## Getting Help

Stuck on something this README does not answer? Start with the guide
for whichever part of the project you are working in:

- [ESPI Full Algorithm/README.md](ESPI%20Full%20Algorithm/README.md): camera and signal generator specific setup (Basler, Allied Vision, the Windows Zadig driver step), troubleshooting, and every dashboard and terminal script explained in detail.
- [espi_app/README.md](espi_app/README.md): the main window itself, its Settings dialog, and its own Troubleshooting section.
- [ESPI Full Algorithm/sdg_control/README.md](ESPI%20Full%20Algorithm/sdg_control/README.md): everything about talking to the signal generator, including a Troubleshooting section for connection problems.

If none of those cover what you are seeing, please open an issue:

1. Go to the project's page on GitHub.
2. Click "Issues" at the top.
3. Click "New Issue".
4. Describe what you were doing, what you expected to happen, and what happened instead. Paste the exact error message if you have one.

Patrick Mulikuza

Professor Hoffman's Lab, Whitman College
