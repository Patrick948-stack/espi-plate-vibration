# Memo: Signal Generator Communication Failure and Fix

**Date:** 2026-07-08
**Prepared by:** Patrick Mulikuza
**Subject:** Root cause and fix for PyVISA timeouts when controlling the Siglent SDG1025 signal generator

---

## Summary

We were unable to reliably send SCPI commands to the Siglent SDG1025 signal generator from Python — every query timed out after 20 seconds. We traced this to PyVISA silently connecting to the wrong hardware resource on Windows. We fixed it by making every script in the project explicitly request PyVISA's pure-Python backend (`@py`) instead of relying on whichever backend the operating system picked by default. After the fix, we verified live against the instrument that identity queries, waveform changes, frequency changes, amplitude changes, and output on/off all work correctly and quickly through the exact code path the experiment pipeline uses.

## The issue

When we ran our signal generator scripts, every command we sent — even a basic `*IDN?` identity query — timed out after the full 20-second wait. This blocked automated control of waveform, frequency, and amplitude, which the ESPI experiment sweep depends on.

## Why it happened

The signal generator is connected over a single USB cable, but it exposes more than one interface to the operating system: a USB Test & Measurement interface (the one meant for SCPI commands) and a serial (COM-port-style) interface. PyVISA relies on a "backend" to discover and talk to instruments, and we had two backends installed on the development machine: NI-VISA (Windows' vendor runtime) and `pyvisa-py` (a pure-Python backend).

`pyvisa.ResourceManager()`, called with no arguments, defaults to whichever backend is available — on this machine, that was NI-VISA. NI-VISA enumerated the instrument only as `ASRL3::INSTR`, the serial interface, not the correct `USB0::...::INSTR` SCPI interface. Every command we sent went to the wrong door: the serial interface doesn't speak SCPI, so nothing ever replied, and every call blocked until PyVISA's timeout expired.

We confirmed this directly: calling `pyvisa.ResourceManager()` (default backend) found only `ASRL3::INSTR` and timed out on every query, while calling `pyvisa.ResourceManager('@py')` found `USB0::62701::60986::SDG10GAC3R0028::0::INSTR` and returned replies in 1–3 milliseconds.

## How we fixed it

We updated every script that opens a VISA connection to this instrument — across both the `signal_generator/` folder and the `ESPI Full Algorithm/` folder — to call:

```python
rm = pyvisa.ResourceManager('@py')
```

instead of the bare `pyvisa.ResourceManager()`. This forces PyVISA to always use the `pyvisa-py` backend, which we had already proven finds the correct `USB0::...::INSTR` resource every time. We applied this change everywhere a `ResourceManager` is created, including `signal_generator_control.py`'s `open_connection()` (the function the actual experiment pipeline calls), `sdg_control/connections.py`, and the standalone debug/test scripts, and updated the docstrings and README to match so the codebase doesn't drift back toward the ambiguous default.

## Why we took this approach

We considered a few alternatives and ruled them out:

- **Uninstalling NI-VISA** would fix the immediate symptom on this machine, but it's an environment-specific workaround, not a code fix — a lab machine with NI-VISA reinstalled (e.g. for another instrument) would silently reintroduce the bug.
- **Hardcoding the resource string** (`USB0::62701::...::INSTR`) would tie the code to one instrument's serial number and one specific USB enumeration, breaking if the unit is swapped or replugged into a different port in a way that changes enumeration.
- **Explicitly requesting `'@py'`** fixes the root cause at the one place it needs fixing — the backend selection — without depending on install order, OS driver priority, or which VISA runtimes happen to be present on a given lab computer. It's also the same backend already required on macOS and Linux (which don't have NI-VISA at all), so this change makes behavior consistent across every OS the project runs on, rather than Windows-only.

## Why it worked

`pyvisa-py` talks to USB instruments through `pyusb`/`libusb` directly, rather than going through NI-VISA's own driver and resource-enumeration logic. Once we forced every connection through `@py`, PyVISA consistently found and opened the instrument's real `USB0::...::INSTR` SCPI interface instead of the serial interface, so commands started reaching the instrument and getting real replies.

We verified this against the live instrument, through the same functions the experiment pipeline calls (`connect_instrument()`, `configure_channel()`, `set_frequency()`, `turn_off_output()` in `signal_generator_control.py`):

- Identity query returned instantly (`SDG,SDG1025,SDG10GAC3R0028,...`)
- Waveform set to SINE — confirmed by reading the setting back
- Frequency set to 1000 Hz — confirmed
- Amplitude set to 1 Vpp — confirmed
- Offset set to 0 V — confirmed
- Output toggled ON, held, then OFF — confirmed

This exercises exactly the control surface (`run_experiment.py` → `complete_pipeline_inclusive.py` / `complete_pipeline.py` / `complete_pipeline_allied_vision.py` → `signal_generator_control.py`) that the frequency sweep uses during a real experiment.

## A related, separate finding (not a blocker)

While isolating the original timeout, we also found that two specific diagnostic queries — `SYST:ERR?` and `STAT:OPER?` — still time out even over the correct `@py`/`USB0` connection, both in sequence and fully isolated with nothing sent before them. We treat this as a firmware-level quirk of this SDG1025 unit, not a bug in our code: neither command is called anywhere in `signal_generator_control.py`'s actual control functions (`configure_channel`, `set_frequency`, `set_waveform`, `set_amplitude`, `set_offset`), only in the standalone debug scripts used to investigate the original issue. It does not affect the experiment pipeline.
