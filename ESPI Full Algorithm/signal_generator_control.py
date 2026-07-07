"""
control_signal_generator.py
Author: Patrick Mulikuza

A self-contained control library for the Siglent SDG1015 signal generator.

Import this file into any script to send waveform commands without touching
the instrument front panel or typing SCPI commands by hand.

WHAT IS SCPI?
-------------
SCPI (Standard Commands for Programmable Instruments) is the language used to
control lab instruments over a cable.  A SCPI command looks like a sentence
with colons separating the parts:
    C1:BSWV FRQ,1000
    ↑  ↑     ↑   ↑
    |  |     |   value to set
    |  |     parameter name
    |  command group (Basic SineWaVe settings)
    channel number

To understand this file, you don't need to master all SCPI commands, all you need is Python knowledge.

WHAT IS VISA?
-------------
VISA (Virtual Instrument Software Architecture) is the standard way computers
talk to lab instruments over USB, GPIB, or Ethernet.  The pyvisa library gives
you a Python interface to it.  You do not need to understand it in detail;
just know that you need it installed: pip install pyvisa pyvisa-py

HOW TO USE IN ANOTHER FILE
---------------------------
Option A — import only the functions you need:

    from control_signal_generator import open_connection, configure_channel, close_connection

Option B — import everything under a short prefix:

    import control_signal_generator as sg

    instr = sg.open_connection()
    sg.configure_channel(instr, waveform="sine", frequency=1000, amplitude=3.0)
    sg.turn_on_output(instr, channel=1)
    sg.close_connection(instr)

Option C — import everything into your current file's namespace:

    from control_signal_generator import *

    instr = open_connection()   # no prefix needed

HOW THIS FILE IS ORGANIZED
---------------------------
  Section 1 — Safety Clamps          : keep values inside the hardware's legal range
  Section 2 — Connection             : open and close VISA sessions
  Section 3 — Status / Query         : read current settings (read-only, no changes)
  Section 4 — Output Control         : turn channel outputs ON and OFF
  Section 5 — Waveform Parameter Setters : set frequency, amplitude, offset, waveform type
  Section 6 — Convenience Wrapper    : configure everything in one call

DEPENDENCIES (install with pip if missing):
    pip install pyvisa pyvisa-py
"""

import os
import pyvisa
import time


# ==============================================================================
# SECTION 0 — ERROR DIAGNOSTICS
# ==============================================================================
# Two kinds of mistake account for almost every crash reported from this file:
#
#   1. A VISA-level communication error — cable unplugged, instrument busy,
#      driver not installed correctly. pyvisa's own e.description is accurate
#      but generic ("Timeout expired before operation completed."). It does
#      not tell you what to actually go check. _describe_visa_error() below
#      translates the handful of error codes this lab's hardware actually
#      produces into a specific, actionable sentence.
#
#   2. Passing None as `instr` — almost always because open_connection()
#      returned None (no instrument found) and the result was used anyway
#      without being checked first. Without a guard this turns into
#      "AttributeError: 'NoneType' object has no attribute 'query'", which
#      does not explain what actually went wrong. _require_instrument()
#      catches this before it reaches pyvisa at all.
#
# Windows needs one extra one-time driver step (Zadig) that Mac and Linux
# don't — see README.md "Signal generator setup (Windows only)". Messages
# below only mention that step when actually running on Windows, so Mac and
# Linux users are not shown irrelevant instructions.
# ==============================================================================

_ON_WINDOWS = os.name == "nt"

# Maps pyvisa's error abbreviation (e.VisaIOError.abbreviation) to a sentence
# that says both what happened AND what to do about it. Any error code not
# listed here falls back to pyvisa's own e.description in _describe_visa_error().
_VISA_ERROR_HELP = {
    "VI_ERROR_TMO": (
        "The signal generator did not respond in time. It may be busy, "
        "mid-command from another program, or the USB connection is "
        "unstable. Wait a moment and try again; if it keeps happening, "
        "unplug and replug the USB cable."
    ),
    "VI_ERROR_RSRC_NFOUND": (
        "The signal generator is no longer reachable at its last known "
        "address. It was likely unplugged, powered off, or moved to a "
        "different USB port. Check the cable and power, then call "
        "open_connection() again."
    ),
    "VI_ERROR_CONN_LOST": (
        "The connection to the signal generator was lost mid-command. "
        "Check that the USB cable is still firmly connected, then call "
        "open_connection() again."
    ),
    "VI_ERROR_RSRC_BUSY": (
        "The signal generator is already in use by another program or "
        "another running copy of this script. Close NI-MAX, any other "
        "Python session talking to it, or a duplicate run of this script, "
        "then try again."
    ),
    "VI_ERROR_RSRC_LOCKED": (
        "The signal generator's connection is locked by another session. "
        "Close any other program talking to it (NI-MAX, another Python "
        "session), then try again."
    ),
    "VI_ERROR_INV_RSRC_NAME": (
        "The instrument address is no longer valid — the list of connected "
        "devices likely changed between finding it and using it. Call "
        "open_connection() again to get a fresh address."
    ),
}


def _describe_visa_error(e):
    """
    Turn a pyvisa.VisaIOError into a specific, actionable sentence.

    Looks up the error's abbreviation (e.g. "VI_ERROR_TMO") in
    _VISA_ERROR_HELP. Falls back to pyvisa's own e.description for any
    error code this lab's hardware hasn't been seen to raise, so nothing
    is ever hidden — worst case you just get pyvisa's original message.

    Example:
        except pyvisa.VisaIOError as e:
            print(f"[ERROR] Could not set frequency: {_describe_visa_error(e)}")
    """
    return _VISA_ERROR_HELP.get(e.abbreviation, e.description)


def _require_instrument(instr, action):
    """
    Return True if instr looks like an open connection, False otherwise.

    Prints a specific message when instr is None instead of letting the
    caller's next line crash with a confusing
    "AttributeError: 'NoneType' object has no attribute ...".

    Args:
        instr  : the value the caller passed in as the instrument handle
        action : short present-tense description of what the caller is
                 trying to do, used in the printed message
                 (e.g. "set the frequency")

    Example:
        def get_identity(instr):
            if not _require_instrument(instr, "read the instrument identity"):
                return None
            ...
    """
    if instr is None:
        print(f"[ERROR] Cannot {action} — no instrument is connected.")
        print("  This usually means open_connection() returned None earlier "
              "(no instrument was found) and that result was used without "
              "being checked first.")
        print("  Call open_connection() again and confirm it does not "
              "return None before sending any commands.")
        return False
    return True


# ==============================================================================
# SECTION 1 — SAFETY CLAMPS
# ==============================================================================
# Every value you send to the instrument must fall inside a legal range.
# If you request a frequency that is too high, the instrument will either
# refuse the command or behave unpredictably.
#
# "Clamping" means silently moving an out-of-range value to the nearest
# allowed boundary.  For example, if the max amplitude is 20 Vpp and you
# request 25 Vpp, clamping gives you 20 Vpp and prints a warning.
#
# These functions are called automatically by the setters in Section 5 — you
# do not normally need to call them yourself, but they are public so you can
# use them to validate values before building a UI or a sweep loop.
#
# WHY CLAMP INSTEAD OF RAISING AN ERROR?
#   In an experiment it is usually better to get a slightly wrong value and
#   keep running than to crash the whole script.  The warning printed to the
#   console tells you what was adjusted so you can fix the input if needed.
# ==============================================================================

def clamp_frequency(frequency, waveform="sine"):
    """
    Adjust a frequency value so it falls within the legal range for the waveform.

    Each waveform type has a different maximum frequency because of how the
    hardware synthesises the signal internally.  A sine wave can go up to 15 MHz,
    but a ramp wave can only reach 300 kHz because generating a perfect triangle
    at high speed is much harder for the electronics.

    If the requested frequency is already inside the legal range, it is returned
    unchanged.  If it is outside, it is moved to the nearest boundary and a
    warning is printed.

    Args:
        frequency (float) : Desired frequency in Hz.
        waveform  (str)   : Waveform type currently set on the channel.
                            Accepted values (case-insensitive):
                            "sine", "square", "ramp", "pulse", "arb", "noise".
                            Defaults to "sine" if omitted.

    Returns:
        float : The (possibly adjusted) frequency in Hz, always within limits.

    Example:
        safe_freq = clamp_frequency(20e6, waveform="ramp")
        # Returns 300000.0 and prints a warning — ramp max is 300 kHz
    """
    # Hardware frequency limits per waveform type  (min Hz, max Hz)
    # These come directly from the SDG1015 datasheet.
    limits = {
        "sine":   (1e-6, 15e6),   # 1 µHz – 15 MHz
        "square": (1e-6, 15e6),   # 1 µHz – 15 MHz
        "ramp":   (1e-6,  3e5),   # 1 µHz – 300 kHz
        "pulse":  (5e-4,  5e6),   # 500 µHz – 5 MHz
        "arb":    (1e-6,  5e6),   # 1 µHz – 5 MHz
        "noise":  (1e-6, 50e6),   # 1 µHz – 50 MHz
    }

    # If an unrecognised waveform name is passed, fall back to sine limits
    # instead of raising a KeyError and crashing the caller.
    min_f, max_f = limits.get(waveform.lower(), (1e-6, 15e6))

    # max(min_f, ...) raises values that are too low;
    # min(..., max_f) lowers values that are too high.
    clamped = max(min_f, min(frequency, max_f))

    if clamped != frequency:
        print(f"[WARNING] Frequency {frequency} Hz is out of range for '{waveform}'. "
              f"Clamped to {clamped} Hz.")
    return clamped


def clamp_amplitude(amplitude):
    """
    Adjust an amplitude so it falls within the SDG1015's output range.

    The instrument can produce signals as small as 2 mVpp (barely detectable)
    and as large as 20 Vpp.  Values outside that window are moved to the
    nearest boundary.

    Args:
        amplitude (float) : Desired peak-to-peak amplitude in Volts (Vpp).
                            "Peak-to-peak" means the total swing from the lowest
                            point of the wave to the highest point.

    Returns:
        float : The (possibly adjusted) amplitude in Vpp.

    Example:
        safe_amp = clamp_amplitude(25.0)
        # Returns 20.0 and prints a warning
    """
    MIN_AMP = 0.002   # 2 mVpp — the smallest signal the hardware can produce
    MAX_AMP = 20.0    # 20 Vpp  — the largest safe output level

    clamped = max(MIN_AMP, min(amplitude, MAX_AMP))

    if clamped != amplitude:
        print(f"[WARNING] Amplitude {amplitude} Vpp is out of range. "
              f"Clamped to {clamped} Vpp.")
    return clamped


def clamp_offset(offset, amplitude=0.0):
    """
    Adjust a DC offset so that the total output stays within ±10 V.

    A DC offset shifts the whole waveform up or down on the voltage axis.
    If you add too large an offset, the peaks of the wave would exceed the
    instrument's internal ±10 V rail and get clipped (cut flat).

    To prevent that, the allowed offset range shrinks as amplitude grows:
        amplitude = 0 Vpp  → offset can be anywhere from -10 V to +10 V
        amplitude = 4 Vpp  → peaks swing ±2 V, so offset is limited to ±8 V
        amplitude = 20 Vpp → peaks swing ±10 V, so offset must be 0 V

    Args:
        offset    (float) : Desired DC offset in Volts (can be negative).
        amplitude (float) : The amplitude currently set on this channel in Vpp.
                            Pass the same value you gave to set_amplitude so
                            the calculation is accurate.  Defaults to 0.

    Returns:
        float : The (possibly adjusted) offset in Volts.

    Example:
        safe_offset = clamp_offset(9.0, amplitude=4.0)
        # Returns 8.0 — a 4 Vpp wave swings ±2 V, leaving only ±8 V for offset
    """
    # Half the amplitude is how far the wave swings away from the offset level.
    # The offset must keep that swing entirely inside the ±10 V rail.
    max_offset = max(0.0, 10.0 - abs(amplitude / 2.0))

    clamped = max(-max_offset, min(offset, max_offset))

    if clamped != offset:
        print(f"[WARNING] Offset {offset} V is out of safe range. "
              f"Clamped to {clamped} V.")
    return clamped


# ==============================================================================
# SECTION 2 — CONNECTION
# ==============================================================================
# These functions open and close the communication link between your computer
# and the signal generator.
#
# HOW THE CONNECTION WORKS:
#   1. pyvisa.ResourceManager() — creates a "manager" object that knows how
#      to speak to instruments over USB, GPIB, or Ethernet.
#   2. rm.list_resources()      — scans all ports and returns the VISA address
#      of every instrument it finds.  A USB address looks like:
#        USB0::62701::60986::SDG10GAC3R0028::0::INSTR
#   3. rm.open_resource(addr)   — opens a session with one specific instrument
#      and returns a handle object.  You pass this handle to every command
#      function.
#
# ALWAYS FOLLOW THIS PATTERN:
#
#   instr = open_connection()
#   if instr is None:
#       print("No instrument found — stopping.")
#   else:
#       # ... send your commands ...
#       close_connection(instr)
#
# Leaving a session open without closing it can prevent other scripts (or the
# next run of this script) from connecting to the same instrument.
# ==============================================================================

def find_instruments(rm):
    """
    Scan for all VISA-compatible instruments connected to the computer right now.

    A VISA resource manager (rm) knows how to talk to instruments over USB,
    GPIB, Ethernet, and other interfaces.  This function asks it to list
    everything it can currently see.

    Args:
        rm : A pyvisa.ResourceManager instance.
             Create one with:  rm = pyvisa.ResourceManager()

    Returns:
        tuple : One VISA address string per detected instrument.
                Example: ('USB0::62701::60986::SDG10GAC3R0028::0::INSTR',)
        None  : If nothing was found.  The caller should check for this and
                stop early rather than trying to connect to a missing device.

    Example:
        rm    = pyvisa.ResourceManager()
        addrs = find_instruments(rm)
        if addrs is None:
            print("No instruments found.")
    """
    try:
        instrs = rm.list_resources()
    except Exception as e:
        # This means the VISA backend itself failed to start — a broken
        # pyvisa/pyvisa-py install, not "no instrument is plugged in".
        print(f"[ERROR] Could not scan for instruments: {e}")
        if _ON_WINDOWS:
            print("  Reinstall the backend: pip install pyvisa pyvisa-py libusb-package")
            print("  Or install NI-VISA instead (see README.md 'Signal generator setup').")
        else:
            print("  Try reinstalling the backend: pip install pyvisa pyvisa-py")
        return None

    if len(instrs) == 0:
        steps = ["Is the signal generator powered on and the USB cable connected?"]
        if _ON_WINDOWS:
            steps.append(
                "(Windows) Has Zadig been used to bind a WinUSB driver to it? "
                "Download: https://zadig.akeo.ie"
            )
            steps.append(
                "(Windows) Is 'libusb-package' installed? "
                "pip install libusb-package"
            )
        else:
            steps.append("Unplug and replug the USB cable, then try again.")
        steps.append(
            'Run: python -c "import usb.core; '
            'print(list(usb.core.find(find_all=True)))" '
            "— an empty list or a 'NoBackendError' confirms the problem is "
            "at the USB driver level, not in this script (see README.md "
            "'Signal generator setup')."
        )

        print("[ERROR] No VISA instruments found.")
        print("  This does not necessarily mean Python or pyvisa are broken "
              "— check, in order:")
        for i, step in enumerate(steps, start=1):
            print(f"    {i}. {step}")
        return None

    print(f"Found {len(instrs)} instrument(s):")
    for i, addr in enumerate(instrs):
        print(f"  [{i}] {addr}")
    return instrs


def connect_instrument(rm, instrs, index=0):
    """
    Open a communication session with one instrument from the detected list.

    The returned object is your handle to the instrument — pass it to every
    function in this file to send commands.

    Args:
        rm          : A pyvisa.ResourceManager instance (same one used in
                      find_instruments).
        instrs      : The tuple returned by find_instruments.
        index (int) : Which instrument in the list to open.  Defaults to 0
                      (the first one found).  Change this only if more than one
                      instrument is connected and you want a specific one.

    Returns:
        instr : An open PyVISA resource object ready to accept commands.
        None  : If index is out of range, or the instrument could not be
                opened (e.g. it was unplugged between find_instruments()
                finding it and this call trying to open it).

    Example:
        rm    = pyvisa.ResourceManager()
        addrs = find_instruments(rm)
        instr = connect_instrument(rm, addrs, index=0)
        if instr is None:
            print("Could not connect.")
    """
    if not instrs:
        print("[ERROR] Cannot connect — no instrument addresses were given.")
        print("  Call find_instruments() first and check it did not return None.")
        return None

    if index < 0 or index >= len(instrs):
        print(f"[ERROR] index={index} is out of range — only {len(instrs)} "
              f"instrument(s) were found (valid indices: 0 to {len(instrs) - 1}).")
        return None

    try:
        instr = rm.open_resource(instrs[index])
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not open a connection to {instrs[index]}: "
              f"{_describe_visa_error(e)}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error opening {instrs[index]}: {e}")
        return None

    # How many milliseconds to wait for a reply before giving up and raising
    # a timeout error.  10 seconds is generous — most commands reply in < 1 s.
    instr.timeout = 10000

    # The character the instrument appends to every message it sends back to us.
    # We tell pyvisa to strip this off automatically so our strings are clean.
    instr.read_termination = '\n'

    # The character pyvisa appends to every command we send to the instrument.
    # The instrument uses this to know that the message is finished.
    instr.write_termination = '\n'

    print(f"Opened connection to: {instrs[index]}")
    return instr


def open_connection(index=0):
    """
    One-call shortcut: create a resource manager, scan for instruments, and
    open the one at the given index — all in a single function.

    This is the easiest way to start from a fresh script.  Instead of three
    separate setup calls you can do:
        instr = open_connection()

    Args:
        index (int) : Which instrument to open when multiple are connected.
                      Defaults to 0 (the first one found).

    Returns:
        instr : An open PyVISA resource object, or None if no instrument found.

    Example:
        instr = open_connection()
        if instr is None:
            print("Could not connect.")
    """
    try:
        rm = pyvisa.ResourceManager()
    except Exception as e:
        print(f"[ERROR] Could not start a VISA resource manager: {e}")
        print("  Make sure both packages are installed: pip install pyvisa pyvisa-py")
        if _ON_WINDOWS:
            print("  On Windows, also make sure the Zadig driver step has been "
                  "done (see README.md 'Signal generator setup (Windows only)'), "
                  "or install NI-VISA instead: https://www.ni.com")
        return None

    instrs = find_instruments(rm)

    if instrs is None:
        return None  # find_instruments() already printed a specific reason

    return connect_instrument(rm, instrs, index=index)


def close_connection(instr):
    """
    Cleanly close the communication session with the instrument.

    Always call this when you are finished sending commands.  Leaving a
    session open can prevent other programs — or the next run of your script —
    from connecting to the same instrument.

    Args:
        instr : The open PyVISA resource object to close.

    Example:
        close_connection(instr)
    """
    if not _require_instrument(instr, "close the connection"):
        return

    try:
        instr.close()
        print("Connection closed.")
    except pyvisa.VisaIOError as e:
        # Usually harmless — the instrument was likely already disconnected
        # or powered off, so there is nothing left to close cleanly.
        print(f"[WARNING] Instrument did not close cleanly: {_describe_visa_error(e)}")


# ==============================================================================
# SECTION 3 — STATUS / QUERY
# ==============================================================================
# These functions READ information from the instrument without changing anything.
#
# In SCPI, a command that ends with "?" is a query — it asks the instrument
# to send back a value rather than setting one.  For example:
#   C1:OUTP?      asks "what is the output state of channel 1?"
#   C1:BSWV?      asks "what are all the waveform settings for channel 1?"
#   *IDN?         asks "who are you?" (standard for all SCPI instruments)
#
# Use these functions to confirm a setting took effect or to inspect the
# instrument state at the start of a session before changing anything.
# ==============================================================================

def get_identity(instr):
    """
    Ask the instrument to identify itself and return the response string.

    Every SCPI-compatible instrument responds to the *IDN? query.  The reply
    is a comma-separated string with four fields:
        Manufacturer, Model, Serial Number, Firmware Version
    Example: "SDG,SDG1025,SDG10GAC3R0028,1.01.01.39R5"

    Useful for verifying you are talking to the right instrument, especially
    when multiple devices are connected.

    Args:
        instr : Open PyVISA resource object.

    Returns:
        str : The identity string from the instrument (whitespace stripped).

    Example:
        identity = get_identity(instr)
        # Prints and returns: "SDG,SDG1015,SDG10GAC3R0028,1.01.01.39R5"
    """
    if not _require_instrument(instr, "read the instrument identity"):
        return None

    try:
        identity = instr.query('*IDN?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read instrument identity: {_describe_visa_error(e)}")
        return None

    print(f"Instrument identity: {identity.strip()}")
    return identity.strip()


def get_output_status(instr, channel=1):
    """
    Check whether the output on a given channel is currently ON or OFF.

    The instrument returns a string like:
        "C1:OUTP ON,LOAD,HZ,PLRT,NOR"
    which tells you the output state, load impedance setting, and polarity.

    Args:
        instr         : Open PyVISA resource object.
        channel (int) : Which channel to check.  Use 1 or 2.  Defaults to 1.

    Returns:
        str : The raw status string from the instrument.

    Example:
        status = get_output_status(instr, channel=1)
        if "ON" in status:
            print("Output is active.")
    """
    if not _require_instrument(instr, f"read the output status for channel {channel}"):
        return None

    try:
        status = instr.query(f'C{channel}:OUTP?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read channel {channel} output status: "
              f"{_describe_visa_error(e)}")
        return None

    print(f"Channel {channel} output status: {status.strip()}")
    return status.strip()


def get_wave_status(instr, channel=1):
    """
    Return all current waveform settings for a channel as a single string.

    The BSWV (Basic SineWaVe) query returns a summary that includes:
    waveform type, frequency, period, amplitude, offset, high/low levels,
    phase, and (for square waves) duty cycle.

    This is the quickest way to see exactly what the instrument is currently
    configured to output on a channel.

    Args:
        instr         : Open PyVISA resource object.
        channel (int) : Which channel to query.  Defaults to 1.

    Returns:
        str : The raw waveform-status string from the instrument.

    Example:
        wave_status = get_wave_status(instr, channel=1)
        # Prints something like:
        # C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,...
    """
    if not _require_instrument(instr, f"read the waveform status for channel {channel}"):
        return None

    try:
        wave_status = instr.query(f'C{channel}:BSWV?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read channel {channel} waveform status: "
              f"{_describe_visa_error(e)}")
        return None

    print(f"\n--- Channel {channel} waveform status ---")
    print(wave_status.strip())
    return wave_status.strip()


# ==============================================================================
# SECTION 4 — OUTPUT CONTROL
# ==============================================================================
# These functions turn a channel's physical output connector ON or OFF.
#
# IMPORTANT: Configuring a waveform (frequency, amplitude, etc.) does NOT
# automatically start the output.  You must call turn_on_output() separately.
#
# WHY IS THERE A time.sleep() AFTER TOGGLING THE OUTPUT?
#   The instrument has a physical relay (a tiny electronic switch) that
#   connects the internal signal to the BNC output connector.  The relay takes
#   a fraction of a second to physically open or close.  If we query the
#   output state too soon after sending the command, the relay may not have
#   finished moving yet, and we would read the old state.  The 0.5-second
#   pause lets the relay settle before we confirm the new state.
#
# TYPICAL USAGE:
#   turn_on_output(instr, channel=1)
#   # ... run your experiment ...
#   turn_off_output(instr, channel=1)
# ==============================================================================

def turn_on_output(instr, channel=1):
    """
    Switch the physical output on a channel ON.

    The BNC connector on the front panel will start producing the configured
    waveform as soon as this command is processed.

    Args:
        instr         : Open PyVISA resource object.
        channel (int) : Which channel to enable.  Use 1 or 2.  Defaults to 1.

    Returns:
        channel  : Updated output channel
        None : If a communication error occurred.

    Example:
        turn_on_output(instr, channel=1)
    """
    if not _require_instrument(instr, f"turn on channel {channel}"):
        return None

    try:
        instr.write(f'C{channel}:OUTP ON')
        time.sleep(0.5)  # Wait for the output relay to close before querying state
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return channel
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn on channel {channel}: {_describe_visa_error(e)}")
        return None


def turn_off_output(instr, channel=1):
    """
    Switch the physical output on a channel OFF.

    The BNC connector will stop producing the signal as soon as this command
    is processed.  The waveform settings are preserved — you can call
    turn_on_output() again later without reconfiguring.

    Args:
        instr         : Open PyVISA resource object.
        channel (int) : Which channel to disable.  Use 1 or 2.  Defaults to 1.

    Returns:
        channel  : Updated output channel 
        None : If a communication error occurred.

    Example:
        turn_off_output(instr, channel=1)
    """
    if not _require_instrument(instr, f"turn off channel {channel}"):
        return None

    try:
        instr.write(f'C{channel}:OUTP OFF')
        time.sleep(0.5)  # Wait for the output relay to open before querying state
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return channel
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn off channel {channel}: {_describe_visa_error(e)}")
        return None


# ==============================================================================
# SECTION 5 — WAVEFORM PARAMETER SETTERS
# ==============================================================================
# These functions change one waveform property at a time on a channel.
#
# Each function:
#   1. Clamps the value to the hardware's legal range (via Section 1 helpers)
#   2. Sends the SCPI write command to the instrument
#   3. Waits 200 ms for the instrument to apply the change
#   4. Queries the instrument to confirm the change took effect
#   5. Returns the value that was actually sent (after clamping)
#
# The 200 ms pause after each write is necessary because the instrument needs
# a moment to update its internal state before it can accurately report back
# the new setting.  Querying without the pause may return the old value.
#
# If you want to set everything at once, use configure_channel() in Section 6.
#
# WAVEFORM TYPES EXPLAINED:
#   sine   — smooth S-shaped oscillation.  Most common for vibration excitation.
#   square — jumps instantly between high and low voltage.  Good for digital timing.
#   ramp   — rises or falls linearly then resets.  Used in sweep testing.
#   pulse  — brief high-voltage spike followed by a long low period.
#   noise  — random voltage fluctuations.  Used for broadband excitation.
#   arb    — arbitrary shape you define yourself by uploading sample points.
#   dc     — constant voltage with no oscillation.
# ==============================================================================

def set_waveform(instr, waveform, channel=1):
    """
    Change the waveform type on a channel (e.g. from sine to square).

    This changes the SHAPE of the output signal.  The amplitude, frequency,
    and offset settings remain the same — only the shape changes.

    Args:
        instr          : Open PyVISA resource object.
        waveform (str) : Waveform name (case-insensitive).  Accepted values:
                           "sine"   — smooth sinusoidal wave
                           "square" — on/off rectangular wave
                           "ramp"   — sawtooth / triangle wave
                           "pulse"  — short-duration voltage spikes
                           "noise"  — white noise (random voltages)
                           "arb"    — arbitrary user-defined waveform
                           "dc"     — constant DC voltage, no oscillation
        channel (int)  : Which channel to configure.  Defaults to 1.

    Returns:
        str  : The waveform key in lowercase that was sent (e.g. "square").
               You can pass this straight to set_frequency() so the correct
               frequency ceiling is applied for that waveform type.
        None : If the waveform name was unrecognised or a communication error occurred.

    Example:
        set_waveform(instr, "square", channel=1)
    """
    if not _require_instrument(instr, f"set the waveform on channel {channel}"):
        return None

    # Map friendly names to the SCPI tokens the instrument understands.
    # The instrument only accepts the uppercase versions on the right.
    waveform_map = {
        "sine":   "SINE",
        "square": "SQUARE",
        "ramp":   "RAMP",
        "pulse":  "PULSE",
        "noise":  "NOISE",
        "arb":    "ARB",
        "dc":     "DC",
    }

    key = waveform.lower().strip()
    if key not in waveform_map:
        print(f"[ERROR] Unknown waveform '{waveform}'. "
              f"Choose from: {', '.join(waveform_map.keys())}")
        return None

    token = waveform_map[key]

    try:
        instr.write(f'C{channel}:BSWV WVTP,{token}')
        time.sleep(0.2)  # Give the instrument time to switch waveform generators internally
        new_status = instr.query(f'C{channel}:BSWV?')

        # Confirm the waveform token actually appears in the instrument's reply.
        if f'WVTP,{token}' in new_status:
            print(f"Channel {channel} waveform set to {token}.")
        else:
            print(f"[WARNING] Waveform may not have changed. "
                  f"Instrument reported: {new_status.strip()}")

        return key

    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set waveform on channel {channel}: "
              f"{_describe_visa_error(e)}")
        return None


def set_frequency(instr, frequency, channel=1, waveform="sine"):
    """
    Set the output frequency on a channel.

    Frequency determines how many complete wave cycles occur per second.
    For example, 1000 Hz means 1 000 cycles per second (1 kHz).

    If the requested frequency is outside the legal range for the chosen
    waveform, it is automatically clamped before being sent.

    Args:
        instr             : Open PyVISA resource object.
        frequency (float) : Desired frequency in Hz.
                            Examples: 500 → 500 Hz,  1000 → 1 kHz,  1e6 → 1 MHz
        channel (int)     : Which channel to configure.  Defaults to 1.
        waveform (str)    : The waveform type currently active on this channel.
                            This is needed to apply the correct frequency ceiling.
                            Should match whatever you last set with set_waveform().
                            Defaults to "sine".

    Returns:
        float : The frequency actually sent to the instrument (after clamping).
        None  : If a communication error occurred.

    Example:
        set_frequency(instr, 5000, channel=1, waveform="sine")   # 5 kHz sine
    """
    if not _require_instrument(instr, f"set the frequency on channel {channel}"):
        return None

    frequency = clamp_frequency(frequency, waveform)

    try:
        instr.write(f'C{channel}:BSWV FRQ,{frequency}')
        time.sleep(0.2)  # Wait for the frequency synthesiser to lock to the new value
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} frequency set to {frequency} Hz.")
        print(f"  New settings: {new_status.strip()}")
        return frequency
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set frequency on channel {channel}: "
              f"{_describe_visa_error(e)}")
        return None


def set_amplitude(instr, amplitude, channel=1):
    """
    Set the peak-to-peak output amplitude on a channel.

    Amplitude is the total voltage swing from the bottom of the wave to the top.
    A sine wave with 2 Vpp swings from -1 V to +1 V (assuming zero offset).

    Values outside the range 2 mVpp–20 Vpp are automatically clamped.

    Args:
        instr             : Open PyVISA resource object.
        amplitude (float) : Desired amplitude in Volts peak-to-peak (Vpp).
        channel (int)     : Which channel to configure.  Defaults to 1.

    Returns:
        float : The amplitude actually sent to the instrument (after clamping).
        None  : If a communication error occurred.

    Example:
        set_amplitude(instr, 3.0, channel=1)   # 3 Vpp output
    """
    if not _require_instrument(instr, f"set the amplitude on channel {channel}"):
        return None

    amplitude = clamp_amplitude(amplitude)

    try:
        instr.write(f'C{channel}:BSWV AMP,{amplitude}')
        time.sleep(0.2)  # Wait for the output DAC to settle at the new level
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} amplitude set to {amplitude} Vpp.")
        print(f"  New settings: {new_status.strip()}")
        return amplitude
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set amplitude on channel {channel}: "
              f"{_describe_visa_error(e)}")
        return None


def set_offset(instr, offset, amplitude=0.0, channel=1):
    """
    Set the DC offset voltage on a channel.

    A DC offset shifts the entire waveform up or down on the voltage axis
    without changing its shape or amplitude.  A +1 V offset on a 2 Vpp sine
    wave makes it swing between 0 V and +2 V instead of -1 V and +1 V.

    The allowed offset range shrinks as amplitude increases — see clamp_offset()
    for the exact calculation.

    Args:
        instr            : Open PyVISA resource object.
        offset (float)   : Desired DC offset in Volts.  Can be negative.
        amplitude (float): The amplitude currently set on this channel in Vpp.
                           Pass the same value you gave to set_amplitude() so
                           the ±10 V rail constraint is enforced correctly.
                           Defaults to 0 if omitted.
        channel (int)    : Which channel to configure.  Defaults to 1.

    Returns:
        float : The offset actually sent to the instrument (after clamping).
        None  : If a communication error occurred.

    Example:
        set_amplitude(instr, 2.0, channel=1)
        set_offset(instr, 1.0, amplitude=2.0, channel=1)
        # Wave now swings between 0 V and 2 V
    """
    if not _require_instrument(instr, f"set the offset on channel {channel}"):
        return None

    offset = clamp_offset(offset, amplitude)

    try:
        instr.write(f'C{channel}:BSWV OFST,{offset}')
        time.sleep(0.2)  # Wait for the DC level to settle before confirming
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} offset set to {offset} V.")
        print(f"  New settings: {new_status.strip()}")
        return offset
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set offset on channel {channel}: "
              f"{_describe_visa_error(e)}")
        return None


# ==============================================================================
# SECTION 6 — CONVENIENCE WRAPPER
# ==============================================================================
# Most of the time you want to set waveform type, frequency, amplitude, and
# offset all at once rather than making four separate calls.
# configure_channel() does exactly that in one line.
#
# It also passes the waveform type to set_frequency() automatically, so the
# correct frequency ceiling is applied without you having to think about it.
#
# TYPICAL USAGE:
#
#   instr = open_connection()
#   configure_channel(instr,
#                     waveform="sine",
#                     frequency=440,     # concert A — 440 Hz
#                     amplitude=2.0,     # 2 Vpp
#                     offset=0.0,        # centred around 0 V
#                     channel=1)
#   turn_on_output(instr, channel=1)
#   # ... run experiment ...
#   turn_off_output(instr, channel=1)
#   close_connection(instr)
# ==============================================================================

def configure_channel(instr, waveform="sine", frequency=1000.0,
                      amplitude=1.0, offset=0.0, channel=1):
    """
    Set all four waveform parameters — type, frequency, amplitude, offset —
    in a single call.

    Internally this calls set_waveform, set_frequency, set_amplitude, and
    set_offset in order.  Each step's result (the clamped value actually sent)
    is passed to the next step where relevant, so everything stays consistent.

    Args:
        instr             : Open PyVISA resource object.
        waveform (str)    : Waveform type.  See set_waveform() for accepted values.
                            Defaults to "sine".
        frequency (float) : Frequency in Hz.  Defaults to 1000 (1 kHz).
        amplitude (float) : Peak-to-peak amplitude in Vpp.  Defaults to 1.0 Vpp.
        offset (float)    : DC offset in Volts.  Defaults to 0 V.
        channel (int)     : Which channel to configure.  Defaults to 1.

    Returns:
        dict : A summary of the values actually applied (after any clamping):
               {
                   "waveform":  "sine",     ← lowercase string or None on error
                   "frequency": 1000.0,     ← float in Hz or None on error
                   "amplitude": 1.0,        ← float in Vpp or None on error
                   "offset":    0.0,        ← float in V or None on error
               }

    Example:
        instr  = open_connection()
        result = configure_channel(instr,
                                   waveform="square",
                                   frequency=5000,
                                   amplitude=2.0,
                                   offset=0.5,
                                   channel=1)
        print(result)
        turn_on_output(instr, channel=1)
        close_connection(instr)
    """
    if not _require_instrument(instr, f"configure channel {channel}"):
        return {
            "waveform": None,
            "frequency": None,
            "amplitude": None,
            "offset": None,
            "channel output": None,
        }

    applied_waveform  = set_waveform(instr, waveform, channel=channel)

    # Pass the waveform that was actually applied (not the original request)
    # to set_frequency, so the clamping uses the correct frequency limits.
    # If set_waveform failed and returned None, fall back to the original string.
    applied_frequency = set_frequency(instr, frequency, channel=channel,
                                      waveform=applied_waveform or waveform)

    applied_amplitude = set_amplitude(instr, amplitude, channel=channel)

    # Pass the amplitude that was actually applied to set_offset so the
    # ±10 V rail constraint calculation is accurate.
    applied_offset    = set_offset(instr, offset,
                                   amplitude=applied_amplitude or amplitude,
                                   channel=channel)
    applied_output_ch = turn_on_output(instr, channel)

    return {
        "waveform":  applied_waveform,
        "frequency": applied_frequency,
        "amplitude": applied_amplitude,
        "offset":    applied_offset,
        "channel output": applied_output_ch,
    }


# ==============================================================================
# __all__ — WHAT GETS EXPORTED WITH "from control_signal_generator import *"
# ==============================================================================
# When someone writes "from control_signal_generator import *", Python only
# exports the names listed here.  This prevents internal imports like pyvisa
# and time from leaking into the caller's namespace.
# ==============================================================================
__all__ = [
    # Section 1: Safety Clamps
    # (included so callers can validate values before building sweep loops or UIs)
    "clamp_frequency",
    "clamp_amplitude",
    "clamp_offset",

    # Section 2: Connection
    "find_instruments",
    "connect_instrument",
    "open_connection",
    "close_connection",

    # Section 3: Status / Query
    "get_identity",
    "get_output_status",
    "get_wave_status",

    # Section 4: Output Control
    "turn_on_output",
    "turn_off_output",

    # Section 5: Waveform Parameter Setters
    "set_waveform",
    "set_frequency",
    "set_amplitude",
    "set_offset",

    # Section 6: Convenience Wrapper
    "configure_channel",
]
