# sdg_control — Siglent SDG1015 Signal Generator Control

## Overview

This package provides a clean, modular Python interface to the Siglent
SDG1015 function generator. It handles connection management, waveform
control, safety clamping, and error handling — everything needed to run
frequency sweeps or other automated measurements.

It replaces what used to be one monolithic `signal_generator_control.py`
file, split into focused modules with matching error-handling behavior
(graceful `None`-instrument handling, translated VISA error messages,
Windows Zadig driver hints) so nothing was lost in the split.

## Quick Start

### Basic Usage

```python
from sdg_control import (
    open_connection, configure_channel, turn_on_output,
    turn_off_output, close_connection
)

instr = open_connection(index=0)
if instr is None:
    print("No signal generator found!")
    exit(1)

configure_channel(instr, waveform="sine", frequency=1000, amplitude=1.0)
turn_on_output(instr, channel=1)  # configure_channel() does not do this itself

# ... do measurements ...

turn_off_output(instr, channel=1)
close_connection(instr)
```

### Frequency Sweep Example

```python
import time
from sdg_control import (
    open_connection, configure_channel, set_frequency,
    turn_on_output, turn_off_output, close_connection
)

instr = open_connection(index=0)

configure_channel(instr, waveform="sine", frequency=100, amplitude=2.0, offset=0.0)
turn_on_output(instr, channel=1)

for freq in range(100, 1001, 100):
    set_frequency(instr, freq, channel=1)
    time.sleep(0.5)  # Wait for plate to settle
    # ... capture camera frames ...

turn_off_output(instr, channel=1)
close_connection(instr)
```

## Module Organization

### connections.py
Connection management: discovering, opening, and closing VISA sessions.

* `get_resource_manager()` — Create a PyVISA resource manager, choosing
  the right backend for the OS (falls back to `@py` on Windows if the
  native VISA backend fails to start)
* `discover_instruments()` — Scan for instruments, retrying with `@py`
  if the native backend reported no USB-looking resource
* `find_instruments(rm)` — List every VISA-visible instrument
* `connect_instrument(rm, instrs, index)` — Open a session with one
  instrument from the list
* `open_connection(index)` — One-call convenience wrapper: discover, then
  connect
* `close_connection(instr)` — Close the session cleanly

### status.py
Read-only queries — never change instrument settings.

* `get_identity(instr)` — Query `*IDN?`
* `get_output_status(instr, channel)` — Raw ON/OFF status string
* `get_wave_status(instr, channel)` — Full waveform-settings string

### output.py
Turn the physical output relay on and off.

* `turn_on_output(instr, channel)` — Enable output. Returns the channel
  number on success, `None` on failure.
* `turn_off_output(instr, channel)` — Disable output. Same return
  convention.

### waveform.py
Set waveform type, frequency, amplitude, and offset.

* `set_waveform(instr, waveform, channel)` — Change waveform type
* `set_frequency(instr, frequency, channel, waveform)` — Change frequency
  (clamped to the waveform's legal range)
* `set_amplitude(instr, amplitude, channel)` — Change amplitude (clamped
  to 2 mVpp – 20 Vpp)
* `set_offset(instr, offset, amplitude, channel)` — Change DC offset
  (clamped to keep the waveform's peaks within the ±10V rail)
* `configure_channel(instr, waveform, frequency, amplitude, offset, channel)`
  — Set all four in one call. **Does not turn the output on** — call
  `turn_on_output()` afterward. This is a deliberate difference from the
  old `signal_generator_control.py`'s `configure_channel()`, which did
  both; here, configuring a channel and enabling its output are kept as
  two separate, single-responsibility calls.

### limits.py
Hardware safety: automatic clamping of out-of-range values.

* `clamp_frequency(frequency, waveform)` — Snap frequency into the legal
  range for the given waveform type (varies: 300 kHz max for ramp, 15 MHz
  for sine/square, etc.)
* `clamp_amplitude(amplitude)` — Snap amplitude into 2 mVpp – 20 Vpp
* `clamp_offset(offset, amplitude)` — Snap offset to stay within the
  ±10V rail, given the current amplitude (the legal range narrows as
  amplitude grows)

### errors.py
Shared error-diagnostics helpers used by every other module.

* `describe_visa_error(e)` — Turn a `pyvisa.VisaIOError` into a specific,
  actionable sentence (e.g. "did not respond in time... unplug and
  replug the USB cable") instead of pyvisa's generic description. Falls
  back to `e.description` for any error code not in the lookup table.
* `require_instrument(instr, action)` — Returns `True` if `instr` looks
  like an open connection; if `instr` is `None`, prints a specific
  message explaining that `open_connection()` probably returned `None`
  and returns `False`, instead of letting the caller's next line crash
  with `AttributeError: 'NoneType' object has no attribute ...`.

### constants.py
Hardware timing constants.

* `COMMAND_SETTLE_S` (0.2s) — Time to wait after a waveform parameter
  change before querying to confirm
* `OUTPUT_SETTLE_S` (0.5s) — Time to wait after toggling output before
  querying — longer than `COMMAND_SETTLE_S` because a physical relay
  takes longer to settle than an electronic parameter change

## Common Tasks

### Check if the Signal Generator is Connected

```python
from sdg_control import open_connection, close_connection

instr = open_connection()
if instr is None:
    print("Signal generator not found. Check USB cable and drivers.")
else:
    print("Connected!")
    close_connection(instr)
```

### Sweep Multiple Frequencies

```python
from sdg_control import (
    open_connection, configure_channel, set_frequency,
    turn_on_output, turn_off_output, close_connection
)

instr = open_connection()
configure_channel(instr, waveform="sine", frequency=100, amplitude=2.0)
turn_on_output(instr, channel=1)

for freq in [100, 200, 300, 500, 1000, 2000, 5000]:
    set_frequency(instr, freq)
    # ... measurements ...

turn_off_output(instr, channel=1)
close_connection(instr)
```

### Handle Errors

Every function accepts `instr=None` and communication failures
gracefully — it prints a `[ERROR]` message explaining what happened and
returns `None` (or `False` for `require_instrument()`) instead of
crashing.

```python
from sdg_control import turn_on_output

result = turn_on_output(instr, channel=1)
if result is None:
    print("Failed to turn on output!")
else:
    print(f"Output is now on for channel {result}")
```

## Troubleshooting

**"No instruments found"**

* Check the USB cable connection to the signal generator
* On Windows: verify the Zadig driver is installed (see the project
  root's `README.md`, "Signal generator setup (Windows only)")
* On Mac/Linux: verify `libusb` is installed

**"Timeout expired" / "did not respond in time"**

* The signal generator may be busy or the USB connection unstable
* Try power-cycling the instrument, or unplug and replug the USB cable

**"Could not set frequency"**

* The requested frequency may be out of range for the current waveform
  type (300 kHz max for ramp waves, 15 MHz for sine/square, for example)
* `set_frequency()` clamps out-of-range values automatically and prints
  a warning rather than failing

## Notes

* Always call `turn_on_output()` after `configure_channel()` — the
  latter does not enable the output itself
* Always call `close_connection()` when finished, to release the VISA
  session
* Settings are not persistent across power cycles (normal for USB
  instruments)
* On Windows, first-time setup requires the Zadig driver (see the
  project root's `README.md`)
