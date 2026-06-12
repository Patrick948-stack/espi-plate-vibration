# SDG1015 Signal Generator Control

Python code for controlling a Siglent SDG1015 signal generator from a
computer, without touching the front panel or paying for LabVIEW.

## Why this exists

Our lab has been running its experiments through LabVIEW, which works
but is expensive and hard to change when you don't know the software
well. This project is one piece of a bigger effort to replace that
setup with free, open Python tools. The end goal is a full Python
workflow for our ESPI experiments: the signal generator drives a
speaker that vibrates an instrument plate, a camera records the
speckle patterns, and Python ties it all together.

This repo handles the signal generator part.

## What it does

- Finds and connects to the instrument over USB
- Sets the waveform type (sine, square, ramp, pulse, noise, etc.)
- Sets frequency, amplitude, and DC offset
- Turns the output on and off
- Checks every value before sending it, so you can't ask the
  instrument for something outside its limits

That last point matters. If you ask for 50 V, the code quietly lowers
it to the safe maximum and prints a warning instead of letting the
command through.

## Folder layout

    signal_generator_project/
    ├── control_signal_generator.py   # original single-file version, kept for reference
    ├── examples/
    │   └── basic_usage.py            # a short working demo
    └── sdg_control/                  # the package you actually import
        ├── __init__.py
        ├── limits.py                 # safety checks (no hardware needed to run these)
        ├── connection.py             # finding and opening the instrument
        ├── status.py                 # read-only checks
        ├── output.py                 # output on/off
        └── waveform.py               # setting waveform, frequency, amplitude, offset

## Setup

You need Python 3 and pyvisa:

    pip install pyvisa

You also need a VISA backend so pyvisa can talk to the USB port.
NI-VISA works, or you can use the pure Python one:

    pip install pyvisa-py

Plug the SDG1015 into the computer over USB and you're ready.

## Quick start

    from sdg_control import open_connection, configure_channel, turn_on_output, close_connection

    instr = open_connection()           # connects to the first instrument found

    configure_channel(instr,
                      waveform="sine",
                      frequency=1000,   # 1 kHz
                      amplitude=3.0,    # 3 Vpp
                      offset=0.0,
                      channel=1)

    turn_on_output(instr, channel=1)

    # ... run your measurement ...

    close_connection(instr)

Or just run the demo:

    python examples/basic_usage.py

## A few things to know

- Nothing runs on import. The instrument only does something when you
  call a function.
- Every setter prints what it actually applied, so you can see in the
  terminal exactly what the instrument is doing.
- Always call `close_connection()` when you're done. An open session
  can block other programs from reaching the instrument.
- The frequency limits depend on the waveform. A sine wave can go up
  to 15 MHz, but a ramp tops out at 300 kHz. The code knows this and
  clamps for you.

## What's coming next

Right now everything runs from scripts and the terminal. A user
interface is still being designed and will come later. The goal is to
make the whole setup friendly enough that anyone in the lab can run a
measurement without writing code. The interface will also bring in
the camera side of the project, so the signal generator and the
Basler camera work together from one place.

Planned pieces for the larger project:

- Camera control for the Basler ace camera (pypylon)
- A frequency sweep tool that steps through a range of frequencies
  and records an image at each one
- A user interface that ties the signal generator and camera together
  into one easy tool

## Author

Patrick Mulikuza
Summer research, Prof. Hoffman's lab
