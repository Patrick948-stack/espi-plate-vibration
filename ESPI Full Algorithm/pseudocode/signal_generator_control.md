# signal_generator_control.py — Plain-Language Pseudocode

## What this file is for

This file talks to a Siglent SDG1015 signal generator over USB. A signal
generator is a lab instrument that produces an electrical waveform (a sine
wave, a square wave, and so on) at a chosen frequency and voltage. In this
project the signal generator drives a small vibration source (a speaker or
shaker) that makes a plate vibrate, so the camera can photograph the
vibration pattern.

The file wraps every command the instrument understands into a plain Python
function, so no SCPI text commands or VISA details need to be written by
hand elsewhere in the project.

## Beginner glossary

- **SCPI** — the text-based language instruments understand, like
  `C1:BSWV FRQ,1000` (channel 1, set frequency to 1000 Hz).
- **VISA** — the communication standard that lets a computer send SCPI text
  over USB, GPIB, or Ethernet. The `pyvisa` library implements it in Python.
- **Vpp (volts peak-to-peak)** — the total voltage swing of a wave, from its
  lowest point to its highest point.
- **Clamping** — silently pulling an out-of-range number back to the nearest
  legal value instead of raising an error, so one bad input does not crash a
  whole experiment.

## Overall structure

The file is organized into seven sections, and every section builds on the
one before it:

0. Error diagnostics — turn a communication failure into a specific,
   actionable sentence, shared by every other section
1. Safety clamps — keep numbers inside hardware limits
2. Connection — open and close the USB link
3. Status queries — read settings without changing them
4. Output control — turn the channel's signal on and off
5. Waveform setters — change frequency, amplitude, offset, shape
6. A convenience wrapper that does steps 2–5 in one call

## Section 0 — Error diagnostics

Almost every crash reported from this file traces back to one of two causes,
so this section handles both once, in one place, instead of every function
re-inventing its own error text.

```
_ON_WINDOWS = True only when running on Windows
    # Windows needs an extra one-time driver step (Zadig) that Mac and
    # Linux don't — see README.md "Signal generator setup (Windows only)".
    # Messages below only mention that step when actually on Windows.

_VISA_ERROR_HELP maps a pyvisa error abbreviation to a sentence that says
    both what happened and what to do about it, e.g.:
        "VI_ERROR_TMO"          -> "didn't respond in time... try again"
        "VI_ERROR_RSRC_NFOUND"  -> "no longer reachable... check the cable"
        "VI_ERROR_RSRC_BUSY"    -> "already in use by another program..."

function _describe_visa_error(visa_error):
    look up visa_error's abbreviation in _VISA_ERROR_HELP
    if found: return that specific sentence
    if not found: return pyvisa's own generic description
        # nothing is ever hidden — worst case you just get pyvisa's
        # original message for an error code this lab hasn't seen before

function _require_instrument(instr, action):
    if instr is nothing:
        print "[ERROR] Cannot {action} — no instrument is connected."
        print "  This usually means open_connection() returned None"
        print "  earlier and that result was used without being checked."
        return False
    return True
```

Every function below that takes `instr` as its first argument calls
`_require_instrument()` first, and every function that catches a
`pyvisa.VisaIOError` prints `_describe_visa_error(e)` instead of the
error's raw, generic description text.

## Section 1 — Safety clamps

```
function clamp_frequency(frequency, waveform):
    look up (min, max) legal frequency for this waveform type
        (sine/square go up to 15 MHz, ramp only 300 kHz, etc.)
    if waveform is not recognized:
        fall back to sine's limits instead of crashing
    push frequency up to min if it is too low
    push frequency down to max if it is too high
    if the value changed:
        print a warning showing the original and clamped value
    return the clamped value

function clamp_amplitude(amplitude):
    clamp between 2 mVpp (quietest signal) and 20 Vpp (loudest signal)
    warn if the value had to change
    return the clamped value

function clamp_offset(offset, amplitude):
    # a DC offset shifts the whole wave up or down; if the offset plus the
    # wave's own swing would exceed +-10V, the instrument would clip the wave
    max_allowed_offset = 10 - half of amplitude
    clamp offset between -max_allowed_offset and +max_allowed_offset
    warn if the value had to change
    return the clamped value
```

These three functions never talk to the instrument — they only do math — so
every waveform setter below calls them first.

## Section 2 — Connection

```
function find_instruments(resource_manager):
    try to ask the resource manager to list every connected VISA device
    if that itself raised an error:
        print "[ERROR] Could not scan for instruments" plus a reinstall
            hint (mentions Zadig/libusb-package only if _ON_WINDOWS)
        return nothing
    if nothing found:
        print a NUMBERED checklist: is it powered on and plugged in?
            (Windows only) has Zadig bound a WinUSB driver? is
            libusb-package installed? then a usb.core command to test
            the driver layer directly, pointing at README.md for detail
        return nothing
    print each device's address
    return the list of addresses

function connect_instrument(resource_manager, address_list, index):
    if address_list is empty:
        print an error and return nothing
    if index is out of range for address_list:
        print an error naming the bad index and how many were found
        return nothing
    try to open a session with the device at address_list[index]
    if that raised a VISA error: print _describe_visa_error(e), return nothing
    if that raised anything else: print "Unexpected error", return nothing
    set a 10 second timeout so a stuck command doesn't hang forever
    tell pyvisa what character marks the end of a message, in and out
    return the open session handle

function open_connection(index):
    # one-call shortcut combining the two functions above
    try to create a resource manager
    if that failed: print "pip install pyvisa pyvisa-py" (+ Zadig hint on
        Windows), return nothing
    addresses = find_instruments(resource_manager)
    if none found: return nothing  # find_instruments() already explained why
    return connect_instrument(resource_manager, addresses, index)

function close_connection(instrument):
    if not _require_instrument(instrument, "close the connection"): return
    try to close the session
    if that raised a VISA error: print _describe_visa_error(e) as a
        [WARNING] — this is usually harmless, the instrument was probably
        already unplugged or powered off
    else: print confirmation
```

Every script in the project follows this pattern: call `open_connection()`,
check whether it returned nothing, and if it returned something call
`close_connection()` once the experiment is finished. `connect_instrument()`
and `open_connection()` can now both return nothing on failure (not just
"no instrument found") — always check the result before using it.

## Section 3 — Status queries (read-only)

```
function get_identity(instrument):
    if not _require_instrument(instrument, "read the instrument identity"):
        return nothing
    try to send the standard "*IDN?" query
    if that raised a VISA error: print _describe_visa_error(e), return nothing
    return the instrument's manufacturer, model, and serial number as text

function get_output_status(instrument, channel):
    if not _require_instrument(...): return nothing
    try to ask "C{channel}:OUTP?"
    if that raised a VISA error: print _describe_visa_error(e), return nothing
    return the raw ON/OFF status text

function get_wave_status(instrument, channel):
    if not _require_instrument(...): return nothing
    try to ask "C{channel}:BSWV?"
    if that raised a VISA error: print _describe_visa_error(e), return nothing
    return a text summary of waveform type, frequency, amplitude, offset, etc.
```

None of these three change anything on the instrument — they only read
current values back. All three now return nothing (instead of crashing) if
`instrument` is nothing or the USB link drops mid-query.

## Section 4 — Output control

```
function turn_on_output(instrument, channel):
    if not _require_instrument(instrument, "turn on channel {channel}"):
        return nothing
    send "C{channel}:OUTP ON"
    wait half a second for the physical relay to close
    query the new status to confirm it changed
    return the channel number, or nothing if a VISA error happened
        (message uses _describe_visa_error(e), not the raw description)

function turn_off_output(instrument, channel):
    same as above, but sends "OUTP OFF"
```

The half-second wait exists because the instrument has a physical switch
(a relay) that takes a moment to move. Querying too soon would read the old
state.

## Section 5 — Waveform parameter setters

Each setter below follows the same pattern: clamp the value, send it, pause
briefly, then read the value back to confirm.

```
function set_waveform(instrument, waveform_name, channel):
    if not _require_instrument(instrument, "set the waveform on channel {channel}"):
        return nothing
    look up the SCPI keyword for the requested waveform name
        (sine -> SINE, square -> SQUARE, ramp -> RAMP, etc.)
    if the name is not recognized:
        print an error listing valid choices and return nothing
    send "C{channel}:BSWV WVTP,{keyword}"
    wait 200ms for the instrument to switch internally
    read back the settings and confirm the new waveform is active
    return the waveform name that was applied

function set_frequency(instrument, frequency, channel, waveform):
    if not _require_instrument(...): return nothing
    frequency = clamp_frequency(frequency, waveform)
    send "C{channel}:BSWV FRQ,{frequency}"
    wait 200ms, then read back the settings
    return the frequency actually sent

function set_amplitude(instrument, amplitude, channel):
    if not _require_instrument(...): return nothing
    amplitude = clamp_amplitude(amplitude)
    send "C{channel}:BSWV AMP,{amplitude}"
    wait 200ms, then read back the settings
    return the amplitude actually sent

function set_offset(instrument, offset, amplitude, channel):
    if not _require_instrument(...): return nothing
    offset = clamp_offset(offset, amplitude)
    send "C{channel}:BSWV OFST,{offset}"
    wait 200ms, then read back the settings
    return the offset actually sent
```

Every setter checks `instrument` is not nothing before doing anything else,
and is wrapped in error handling: if the USB communication fails
mid-command, `_describe_visa_error(e)` prints a specific, actionable message
and the function returns nothing instead of crashing the whole experiment.

## Section 6 — Convenience wrapper

```
function configure_channel(instrument, waveform, frequency, amplitude, offset, channel):
    if not _require_instrument(instrument, "configure channel {channel}"):
        return a dictionary with all five values set to nothing
        # checked once here so a missing instrument prints ONE clear
        # message instead of five (one from each sub-call below)

    applied_waveform  = set_waveform(instrument, waveform, channel)
    applied_frequency = set_frequency(instrument, frequency, channel,
                                       waveform = applied_waveform or waveform)
    applied_amplitude = set_amplitude(instrument, amplitude, channel)
    applied_offset    = set_offset(instrument, offset,
                                    amplitude = applied_amplitude or amplitude,
                                    channel)
    applied_output    = turn_on_output(instrument, channel)
    return a dictionary with all four applied values plus the output channel
```

This is the function most other files in the project call — it sets
everything needed for one measurement (shape, frequency, loudness, and
centering) and switches the signal on, all in a single line of calling code.
