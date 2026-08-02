# ESPI Full Algorithm/sdg_control/ - Signal Generator Control Package

## Purpose

Talks to the Siglent SDG1015 signal generator over USB: finding it,
connecting, setting a waveform and frequency, turning its output on and
off, and disconnecting cleanly. Used by every pipeline
(`complete_pipeline*.py`) to drive the speaker during a frequency sweep,
and by `run_experiment_gui.py`'s Setup page for amplitude and offset.

This replaces an older single file, `signal_generator_control.py`, that
no longer exists in this project. All of its logic now lives here,
split into seven small files by responsibility, instead of one large
file.

## Beginner Glossary

- **VISA**: Virtual Instrument Software Architecture, an industry
  standard for talking to lab instruments (signal generators,
  oscilloscopes, and similar equipment) over USB, GPIB, or a network,
  using the same underlying commands regardless of manufacturer.
- **PyVISA**: the Python library that speaks VISA. This package is a
  thin, project specific layer on top of it.
- **Package**: a folder containing an `__init__.py` file, which lets
  Python treat the folder as one importable unit
  (`from sdg_control import open_connection`).

## How the Seven Files Divide the Work

```
sdg_control/
    __init__.py     - gathers every function below into one importable namespace
    connections.py  - discover_instruments, connect_instrument, open_connection, close_connection
    status.py       - get_identity, get_output_status, get_wave_status (read only)
    output.py       - turn_on_output, turn_off_output
    waveform.py     - set_waveform, set_frequency, set_amplitude, set_offset, configure_channel
    limits.py       - clamp_frequency, clamp_amplitude, clamp_offset (pure math, no hardware)
    constants.py    - COMMAND_SETTLE_S, OUTPUT_SETTLE_S (hardware timing constants)
    errors.py       - describe_visa_error, require_instrument (shared error handling)
```

`waveform.py` calls into `limits.py` before sending any value to the
instrument, so a frequency, amplitude, or offset that is out of range
gets snapped to the nearest legal value instead of being rejected or
silently accepted as something the hardware cannot actually do.
`connections.py`, `output.py`, and `waveform.py` all call into
`errors.py` whenever something goes wrong, so every function in this
package fails the same way: a specific, actionable printed message and
a `None` return value, never a raw traceback.

### connections.py: Finding and Opening the Instrument

1. `get_resource_manager()`: create a PyVISA resource manager. On
   Windows, try the native VISA backend first, falling back to the
   pure Python `@py` backend if that fails to start. On Mac and Linux,
   always use `@py` directly.
2. `find_instruments(rm)`: ask the resource manager to scan for every
   VISA-visible device. Print a specific, numbered checklist if nothing
   is found, instead of just "not found".
3. `discover_instruments()`: combine the two steps above, and on
   Windows, retry once with the `@py` backend specifically if the first
   attempt did not report anything that looks like a real USB
   instrument address (a known failure mode where a native backend
   reports the signal generator's serial interface instead of its
   SCPI interface).
4. `connect_instrument(rm, instrs, index)`: open a session with one
   instrument from the discovered list, and configure its
   timeout and line termination.
5. `open_connection(index)`: the one call most scripts actually use.
   Runs discovery and connects to the instrument at `index` in one
   step, returning `None` at any failure instead of raising.
6. `close_connection(instr)`: close the session.

### status.py: Read Only Queries

Ask the instrument questions without changing anything: its identity
string (`*IDN?`), whether a channel's output is currently on or off,
and the full waveform settings string for a channel.

### output.py: The Physical Output Relay

`turn_on_output()` and `turn_off_output()` flip the instrument's output
relay. Neither one is called automatically by `configure_channel()`
below; turning the output on is always a separate, explicit step.

### waveform.py: Waveform, Frequency, Amplitude, Offset

Four single purpose setters (`set_waveform`, `set_frequency`,
`set_amplitude`, `set_offset`), plus `configure_channel()`, a
convenience wrapper that calls all four in one call. `configure_channel()`
deliberately does not turn the output on itself, that is a conscious
design choice (see Why This Design below), and every value it sends
passes through `limits.py`'s clamps first.

### limits.py: Hardware Safety Clamps

Pure functions, no hardware access, easy to unit test alone:

- `clamp_frequency(frequency, waveform)`: legal range depends on
  waveform type (for example, 300 kHz max for a ramp wave, 15 MHz for
  sine or square)
- `clamp_amplitude(amplitude)`: 2 mVpp to 20 Vpp
- `clamp_offset(offset, amplitude)`: keeps the waveform's peaks inside
  the instrument's +/-10V rail; the legal range narrows as amplitude
  grows

### constants.py: Hardware Timing

Two numbers: how long to wait after changing a waveform parameter
before trusting a readback (`COMMAND_SETTLE_S`, 0.2s), and how long to
wait after toggling the output relay before trusting a readback
(`OUTPUT_SETTLE_S`, 0.5s, longer because a physical relay is slower
than an electronic parameter change).

### errors.py: Shared Error Diagnostics

- `describe_visa_error(e)`: turns a generic `pyvisa.VisaIOError` into a
  specific, actionable sentence (for example, explaining that a timeout
  usually means "unplug and replug the USB cable"), instead of
  PyVISA's own generic description.
- `require_instrument(instr, action)`: the guard every public function
  in this package calls first. If `instr` is `None` (meaning
  `open_connection()` already failed earlier), print a clear message
  explaining that, and return `False`, instead of letting the real call
  crash with `AttributeError: 'NoneType' object has no attribute ...`.

## Why This Design

- **One file, one responsibility**: connecting, reading status, writing
  output state, and writing waveform settings are different concerns,
  so they live in different files instead of one large file with
  everything mixed together.
- **Configuring and enabling output are separate calls**: an earlier
  version of this project's `configure_channel()` turned the output on
  as a side effect of configuring it. Splitting them means a caller can
  change frequency mid-sweep, for example, without ever risking an
  unexpected moment where the output is briefly in the wrong state.
- **Clamping instead of rejecting**: an out of range value is far more
  likely to be a typo or a unit mistake (volts instead of millivolts,
  for example) than a deliberate request to break the hardware, so this
  package snaps the value into range and prints a warning, rather than
  stopping the whole experiment over it.
- **`None` on failure, never a crash**: every public function accepts
  `instr=None` and every hardware call is wrapped so a disconnected or
  misbehaving instrument produces a specific printed explanation and a
  `None`/`False` return, not a raw Python traceback a beginner would
  have to decode.

## Related Files

- `complete_pipeline.py`, `complete_pipeline_inclusive.py`,
  `complete_pipeline_allied_vision.py`: call `open_connection()`,
  `configure_channel()`, `set_frequency()`, `turn_on_output()`,
  `turn_off_output()`, and `close_connection()` during a sweep
- `run_experiment_gui.py`: the Setup page's amplitude and offset
  fields reach the instrument through `configure_channel()`
- [sdg_control/README.md](../../ESPI%20Full%20Algorithm/sdg_control/README.md):
  the full reference documentation for this package, including
  copy-paste examples and a Troubleshooting section
