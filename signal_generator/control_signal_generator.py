"""
control_signal_generator.py
Author: Patrick Mulikuza

Drop-in control library for the Siglent SDG1015 signal generator.
Import this file into any script to send waveform commands without touching
the instrument front panel or typing SCPI commands by hand.

Quick-start example:
    from control_signal_generator import open_connection, configure_channel, close_connection

    instr = open_connection(index=0)          # connect to the first detected instrument
    configure_channel(instr,
                      waveform="sine",
                      frequency=1000,         # 1 kHz
                      amplitude=3.0,          # 3 Vpp
                      offset=0.0,             # no DC shift
                      channel=1)
    close_connection(instr)

Nothing in this file runs at import time, every action requires an explicit function call.

Dependencies:
    pyvisa  — VISA communication layer  (pip install pyvisa)
    time    — standard library, used for short hardware-settling delays
"""

import pyvisa
import time


# ---------------------------------------------------------------------------
# Clamping helpers
# These keep every value inside the hardware's legal range before it is
# sent to the instrument, so the instrument never receives a command that
# it cannot execute or that could damage it.
# ---------------------------------------------------------------------------

def clamp_frequency(frequency, waveform="sine"):
    """
    Adjusts a frequency to stay within the legal range for the chosen waveform.

    Each waveform type on the SDG1015 has a different maximum frequency because
    of how the hardware synthesises the signal.  If you ask for a frequency
    that is too high or too low, this function silently moves it to the nearest
    allowed value and prints a warning so you know it happened.

    Parameters:
        frequency (float) : Desired frequency in Hz.
        waveform  (str)   : Waveform type that is (or will be) active on the
                            instrument.  Accepted values (case-insensitive):
                            "sine", "square", "ramp", "pulse", "arb", "noise".
                            Defaults to "sine" when omitted.

    Returns:
        float : The (possibly adjusted) frequency in Hz, always within limits.
    """
    # Hardware frequency limits per waveform type  (min Hz, max Hz)
    limits = {
        "sine":   (1e-6, 15e6),   # 1 µHz – 15 MHz
        "square": (1e-6, 15e6),   # 1 µHz – 15 MHz
        "ramp":   (1e-6,  3e5),   # 1 µHz – 300 kHz
        "pulse":  (5e-4,  5e6),   # 500 µHz – 5 MHz
        "arb":    (1e-6,  5e6),   # 1 µHz – 5 MHz
        "noise":  (1e-6, 50e6),   # 1 µHz – 50 MHz
    }
    # If an unrecognised waveform name is passed, fall back to sine limits instead of raising a KeyError
    min_f, max_f = limits.get(waveform.lower(), (1e-6, 15e6))

    # max(min_f, ...) raises values that are too low;
    # min(..., max_f) lowers values that are too high
    clamped = max(min_f, min(frequency, max_f))

    if clamped != frequency:
        print(f"[WARNING] Frequency {frequency} Hz is out of range for '{waveform}'. "
              f"Clamped to {clamped} Hz.")
    return clamped


def clamp_amplitude(amplitude):
    """
    Adjusts an amplitude to stay within the SDG1015's output range.

    The instrument can produce signals as small as 2 mVpp (barely a whisper)
    and as large as 20 Vpp.  Values outside that range are moved to the
    nearest boundary.

    Parameters:
        amplitude (float) : Desired peak-to-peak amplitude in Volts (Vpp).

    Returns:
        float : The (possibly adjusted) amplitude in Vpp.
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
    Adjusts a DC offset so that the total output signal never exceeds the
    instrument's internal ±10 V voltage rail.

    Think of it this way: if the amplitude is 4 Vpp, the signal swings ±2 V
    around whatever offset you choose.  The offset can therefore be at most
    ±8 V before the peak of the wave would hit 10 V and clip.  This function
    enforces that constraint automatically.

    Parameters:
        offset    (float) : Desired DC offset in Volts (positive or negative).
        amplitude (float) : Current amplitude in Vpp.  Pass the same value you
                            gave to set_amplitude so the calculation is correct.
                            Defaults to 0 if omitted.

    Returns:
        float : The (possibly adjusted) offset in Volts.
    """
    # Half the amplitude is how far the wave swings from the offset.
    # The offset must keep that swing inside the ±10 V rail.
    max_offset = max(0.0, 10.0 - abs(amplitude / 2.0))

    clamped = max(-max_offset, min(offset, max_offset))

    if clamped != offset:
        print(f"[WARNING] Offset {offset} V is out of safe range. "
              f"Clamped to {clamped} V.")
    return clamped


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def find_instruments(rm):
    """
    Scans for all VISA-compatible instruments currently connected to the computer.

    A VISA resource manager (rm) acts like a traffic controller — it knows how
    to talk to instruments over USB, GPIB, Ethernet, and other interfaces.
    This function asks it to list everything it can see right now.

    Parameters:
        rm : A pyvisa.ResourceManager instance.
             Create one with:  rm = pyvisa.ResourceManager()

    Returns:
        tuple : One VISA address string per detected instrument.
                Example: ('USB0::62701::60986::SDG10GAC3R0028::0::INSTR',)
        None  : If nothing was found (caller should check for this and exit early).
    """
    instrs = rm.list_resources()

    if len(instrs) == 0:
        print("[ERROR] No instruments found. Check USB connection and driver.")
        return None

    print(f"Found {len(instrs)} instrument(s):")
    for i, addr in enumerate(instrs):
        print(f"  [{i}] {addr}")
    return instrs


def connect_instrument(rm, instrs, index=0):
    """
    Opens a communication session with one instrument from the detected list.

    Once opened, the returned object is your handle to the instrument — pass it
    to every other function in this file to send commands.

    Parameters:
        rm      : A pyvisa.ResourceManager instance (the same one passed to
                  find_instruments).
        instrs  : The tuple returned by find_instruments.
        index (int) : Position in the instrs tuple to open.  Defaults to 0
                      (the first instrument found).  Change this if more than
                      one instrument is connected and you want a specific one.

    Returns:
        instr : An open PyVISA resource object ready to accept commands.
    """
    instr = rm.open_resource(instrs[index])

    # How long to wait (ms) for the instrument to reply before giving up
    instr.timeout = 10000

    # The character that marks the end of a message coming FROM the instrument
    instr.read_termination = '\n'

    # The character appended to every command sent TO the instrument
    instr.write_termination = '\n'

    print(f"Opened connection to: {instrs[index]}")
    return instr


def open_connection(index=0):
    """
    One-call convenience wrapper: creates a resource manager, scans for
    instruments, and opens the one at the given index.

    This is the easiest way to start from a fresh script.  Instead of three
    separate calls you can do:
        instr = open_connection()

    Parameters:
        index (int) : Which instrument to open when multiple are connected.
                      Defaults to 0 (the first one found).

    Returns:
        instr : An open PyVISA resource object, or None if no instrument found.
    """
    rm = pyvisa.ResourceManager()
    instrs = find_instruments(rm)

    if instrs is None:
        return None  # No instrument connected — caller should handle this

    return connect_instrument(rm, instrs, index=index)


def close_connection(instr):
    """
    Cleanly closes the communication session with the instrument.

    Always call this when you are done.  Leaving a session open can prevent
    other programs from connecting to the same instrument.

    Parameters:
        instr : The open PyVISA resource object to close.

    Returns:
        Nothing.
    """
    instr.close()
    print("Connection closed.")


# ---------------------------------------------------------------------------
# Query / status functions  (read-only — these do not change any settings)
# ---------------------------------------------------------------------------

def get_identity(instr):
    """
    Asks the instrument to identify itself and returns the response.

    The reply is a comma-separated string:
        Manufacturer, Model, Serial Number, Firmware Version
    Example: "SDG,SDG1025,SDG10GAC3R0028,1.01.01.39R5"

    Parameters:
        instr : Open PyVISA resource object.

    Returns:
        str : The raw identity string from the instrument.
    """
    identity = instr.query('*IDN?')
    print(f"Instrument identity: {identity.strip()}")
    return identity.strip()


def get_output_status(instr, channel=1):
    """
    Checks whether the output on a given channel is currently ON or OFF.

    Parameters:
        instr       : Open PyVISA resource object.
        channel (int) : Channel number to check.  Use 1 or 2.  Defaults to 1.

    Returns:
        str : The raw status string from the instrument (e.g. "C1:OUTP ON,...").
    """
    status = instr.query(f'C{channel}:OUTP?')
    print(f"Channel {channel} output status: {status.strip()}")
    return status.strip()


def get_wave_status(instr, channel=1):
    """
    Returns all current waveform settings for a channel as a single string.

    The response contains: waveform type, frequency, period, amplitude, offset,
    high/low levels, phase, and (for square waves) duty cycle.

    Parameters:
        instr       : Open PyVISA resource object.
        channel (int) : Channel to query.  Defaults to 1.

    Returns:
        str : The raw waveform-status string from the instrument.
    """
    wave_status = instr.query(f'C{channel}:BSWV?')
    print(f"\n--- Channel {channel} waveform status ---")
    print(wave_status.strip())
    return wave_status.strip()


# ---------------------------------------------------------------------------
# Output control
# ---------------------------------------------------------------------------

def turn_on_output(instr, channel=1):
    """
    Switches the output of a channel ON.

    The function waits 0.5 seconds after sending the ON command before
    confirming the status.  That pause is necessary because the instrument
    takes a moment to physically close the output relay.

    Parameters:
        instr       : Open PyVISA resource object.
        channel (int) : Channel to enable.  Defaults to 1.

    Returns:
        str : Updated output-status string, or None if a communication error occurs.
    """
    try:
        instr.write(f'C{channel}:OUTP ON')
        time.sleep(0.5)  # Wait for the relay to close before we query its state
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return status.strip()
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn on channel {channel}: {e.description}")
        return None


def turn_off_output(instr, channel=1):
    """
    Switches the output of a channel OFF.

    Parameters:
        instr       : Open PyVISA resource object.
        channel (int) : Channel to disable.  Defaults to 1.

    Returns:
        str : Updated output-status string, or None if a communication error occurs.
    """
    try:
        instr.write(f'C{channel}:OUTP OFF')
        time.sleep(0.5)  # Wait for the relay to open before we query its state
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return status.strip()
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn off channel {channel}: {e.description}")
        return None


# ---------------------------------------------------------------------------
# Waveform parameter setters
# ---------------------------------------------------------------------------

def set_waveform(instr, waveform, channel=1):
    """
    Changes the waveform type on a channel (e.g. from sine to square).

    Parameters:
        instr         : Open PyVISA resource object.
        waveform (str): Waveform name.  Accepted values (case-insensitive):
                          "sine"   — smooth sinusoidal wave
                          "square" — on/off rectangular wave
                          "ramp"   — sawtooth / triangle wave
                          "pulse"  — short-duration pulses
                          "noise"  — white noise
                          "arb"    — arbitrary user-defined waveform
                          "dc"     — constant DC voltage
        channel (int) : Channel to configure.  Defaults to 1.

    Returns:
        str  : The waveform key in lowercase that was applied (e.g. "square").
               Useful for passing straight to set_frequency so the correct
               frequency ceiling is applied.
        None : If the waveform name is unrecognised or a communication error occurs.
    """
    # Map friendly names to the SCPI tokens the instrument understands
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
        time.sleep(0.2)  # Short pause so the instrument has time to apply the change
        new_status = instr.query(f'C{channel}:BSWV?')

        if f'WVTP,{token}' in new_status:
            print(f"Channel {channel} waveform set to {token}.")
        else:
            print(f"[WARNING] Waveform may not have changed. "
                  f"Instrument reported: {new_status.strip()}")

        return key

    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set waveform: {e.description}")
        return None


def set_frequency(instr, frequency, channel=1, waveform="sine"):
    """
    Sets the output frequency on a channel.

    If the requested frequency is outside the hardware limit for the chosen
    waveform, it is automatically clamped to the nearest legal value.

    Parameters:
        instr            : Open PyVISA resource object.
        frequency (float): Desired frequency in Hz (e.g. 1000 for 1 kHz).
        channel (int)    : Channel to configure.  Defaults to 1.
        waveform (str)   : Active waveform type — needed to apply the correct
                           frequency ceiling.  Should match whatever waveform
                           is currently set on that channel.  Defaults to "sine".

    Returns:
        float : The frequency that was actually sent to the instrument (after
                any clamping).  Returns None on communication error.
    """
    frequency = clamp_frequency(frequency, waveform)

    try:
        instr.write(f'C{channel}:BSWV FRQ,{frequency}')
        time.sleep(0.2)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} frequency set to {frequency} Hz.")
        print(f"  New settings: {new_status.strip()}")
        return frequency
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set frequency: {e.description}")
        return None


def set_amplitude(instr, amplitude, channel=1):
    """
    Sets the peak-to-peak output amplitude on a channel.

    Parameters:
        instr             : Open PyVISA resource object.
        amplitude (float) : Desired amplitude in Volts peak-to-peak (Vpp).
                            The range is 2 mVpp to 20 Vpp; values outside
                            that are clamped automatically.
        channel (int)     : Channel to configure.  Defaults to 1.

    Returns:
        float : The amplitude that was actually sent to the instrument (after
                any clamping).  Returns None on communication error.
    """
    amplitude = clamp_amplitude(amplitude)

    try:
        instr.write(f'C{channel}:BSWV AMP,{amplitude}')
        time.sleep(0.2)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} amplitude set to {amplitude} Vpp.")
        print(f"  New settings: {new_status.strip()}")
        return amplitude
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set amplitude: {e.description}")
        return None


def set_offset(instr, offset, amplitude=0.0, channel=1):
    """
    Sets the DC offset voltage on a channel.

    A positive offset shifts the whole waveform upward; a negative offset
    shifts it downward.  The allowed range shrinks as amplitude increases,
    because the peaks of the wave must never exceed the ±10 V output rail.

    Parameters:
        instr           : Open PyVISA resource object.
        offset (float)  : Desired DC offset in Volts.
        amplitude (float): The amplitude currently set on this channel in Vpp.
                           Pass the same value you gave to set_amplitude so the
                           rail-constraint check is accurate.  Defaults to 0.
        channel (int)   : Channel to configure.  Defaults to 1.

    Returns:
        float : The offset that was actually sent to the instrument (after
                any clamping).  Returns None on communication error.
    """
    offset = clamp_offset(offset, amplitude)

    try:
        instr.write(f'C{channel}:BSWV OFST,{offset}')
        time.sleep(0.2)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} offset set to {offset} V.")
        print(f"  New settings: {new_status.strip()}")
        return offset
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set offset: {e.description}")
        return None


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def configure_channel(instr, waveform="sine", frequency=1000.0,
                      amplitude=1.0, offset=0.0, channel=1):
    """
    Sets all four waveform parameters — type, frequency, amplitude, and offset —
    in a single call.

    This is the most convenient way to program a channel from another script.
    It calls set_waveform, set_frequency, set_amplitude, and set_offset in
    order, so you do not have to manage each step yourself.

    Parameters:
        instr             : Open PyVISA resource object.
        waveform (str)    : Waveform type.  See set_waveform for accepted values.
                            Defaults to "sine".
        frequency (float) : Frequency in Hz.  Defaults to 1000 (1 kHz).
        amplitude (float) : Peak-to-peak amplitude in Vpp.  Defaults to 1.0 Vpp.
        offset (float)    : DC offset in Volts.  Defaults to 0 V.
        channel (int)     : Channel to configure.  Defaults to 1.

    Returns:
        dict : A summary of the values actually applied (after clamping):
               {"waveform": ..., "frequency": ..., "amplitude": ..., "offset": ...}
               Values are None for any step that encountered an error.

    Example:
        instr = open_connection()
        turn_on_output(instr, channel=1)
        result = configure_channel(instr,
                                   waveform="square",
                                   frequency=5000,
                                   amplitude=2.0,
                                   offset=0.5,
                                   channel=1)
        print(result)
        close_connection(instr)
    """
    applied_waveform  = set_waveform(instr,  waveform,  channel=channel)
    applied_frequency = set_frequency(instr, frequency, channel=channel,
                                      waveform=applied_waveform or waveform)
    applied_amplitude = set_amplitude(instr, amplitude, channel=channel)
    applied_offset    = set_offset(instr,    offset,
                                   amplitude=applied_amplitude or amplitude,
                                   channel=channel)

    return {
        "waveform":  applied_waveform,
        "frequency": applied_frequency,
        "amplitude": applied_amplitude,
        "offset":    applied_offset,
    }
