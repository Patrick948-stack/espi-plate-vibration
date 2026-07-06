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

The file is organized into six sections, and every section builds on the one
before it:

1. Safety clamps — keep numbers inside hardware limits
2. Connection — open and close the USB link
3. Status queries — read settings without changing them
4. Output control — turn the channel's signal on and off
5. Waveform setters — change frequency, amplitude, offset, shape
6. A convenience wrapper that does steps 2–5 in one call

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
    ask the resource manager to list every connected VISA device
    if nothing found:
        print an error and return nothing
    print each device's address
    return the list of addresses

function connect_instrument(resource_manager, address_list, index):
    open a session with the device at address_list[index]
    set a 10 second timeout so a stuck command doesn't hang forever
    tell pyvisa what character marks the end of a message, in and out
    return the open session handle

function open_connection(index):
    # one-call shortcut combining the two functions above
    create a resource manager
    addresses = find_instruments(resource_manager)
    if none found: return nothing
    return connect_instrument(resource_manager, addresses, index)

function close_connection(instrument):
    close the session
    print confirmation
```

Every script in the project follows this pattern: call `open_connection()`,
check whether it returned nothing, and if it returned something call
`close_connection()` once the experiment is finished.

## Section 3 — Status queries (read-only)

```
function get_identity(instrument):
    send the standard "*IDN?" query
    return the instrument's manufacturer, model, and serial number as text

function get_output_status(instrument, channel):
    ask "C{channel}:OUTP?"
    return the raw ON/OFF status text

function get_wave_status(instrument, channel):
    ask "C{channel}:BSWV?"
    return a text summary of waveform type, frequency, amplitude, offset, etc.
```

None of these three change anything on the instrument — they only read
current values back.

## Section 4 — Output control

```
function turn_on_output(instrument, channel):
    send "C{channel}:OUTP ON"
    wait half a second for the physical relay to close
    query the new status to confirm it changed
    return the channel number, or nothing if a communication error happened

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
    look up the SCPI keyword for the requested waveform name
        (sine -> SINE, square -> SQUARE, ramp -> RAMP, etc.)
    if the name is not recognized:
        print an error listing valid choices and return nothing
    send "C{channel}:BSWV WVTP,{keyword}"
    wait 200ms for the instrument to switch internally
    read back the settings and confirm the new waveform is active
    return the waveform name that was applied

function set_frequency(instrument, frequency, channel, waveform):
    frequency = clamp_frequency(frequency, waveform)
    send "C{channel}:BSWV FRQ,{frequency}"
    wait 200ms, then read back the settings
    return the frequency actually sent

function set_amplitude(instrument, amplitude, channel):
    amplitude = clamp_amplitude(amplitude)
    send "C{channel}:BSWV AMP,{amplitude}"
    wait 200ms, then read back the settings
    return the amplitude actually sent

function set_offset(instrument, offset, amplitude, channel):
    offset = clamp_offset(offset, amplitude)
    send "C{channel}:BSWV OFST,{offset}"
    wait 200ms, then read back the settings
    return the offset actually sent
```

Every setter is wrapped in error handling: if the USB communication fails
mid-command, an error message prints and the function returns nothing instead
of crashing the whole experiment.

## Section 6 — Convenience wrapper

```
function configure_channel(instrument, waveform, frequency, amplitude, offset, channel):
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
