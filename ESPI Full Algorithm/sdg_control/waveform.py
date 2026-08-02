"""
waveform.py
Setting waveform type, frequency, amplitude, and offset, plus the
configure_channel convenience wrapper.
"""

import time
import pyvisa

from .limits import clamp_frequency, clamp_amplitude, clamp_offset
from .constants import COMMAND_SETTLE_S
from .errors import describe_visa_error, require_instrument

WAVEFORM_MAP = {
    "sine":   "SINE",
    "square": "SQUARE",
    "ramp":   "RAMP",
    "pulse":  "PULSE",
    "noise":  "NOISE",
    "arb":    "ARB",
    "dc":     "DC",
}


def set_waveform(instr, waveform, channel=1):
    """Set the waveform type. Returns the applied key (lowercase) or None."""
    if not require_instrument(instr, f"set the waveform on channel {channel}"):
        return None

    key = waveform.lower().strip()
    if key not in WAVEFORM_MAP:
        print(f"[ERROR] Unknown waveform '{waveform}'. "
              f"Choose from: {', '.join(WAVEFORM_MAP.keys())}")
        return None

    token = WAVEFORM_MAP[key]
    try:
        instr.write(f'C{channel}:BSWV WVTP,{token}')
        time.sleep(COMMAND_SETTLE_S)
        new_status = instr.query(f'C{channel}:BSWV?')
        if f'WVTP,{token}' in new_status:
            print(f"Channel {channel} waveform set to {token}.")
        else:
            print(f"[WARNING] Waveform may not have changed. "
                  f"Instrument reported: {new_status.strip()}")
        return key
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set waveform on channel {channel}: {describe_visa_error(e)}")
        return None


def set_frequency(instr, frequency, channel=1, waveform="sine"):
    """Set frequency in Hz (clamped to the waveform's legal range)."""
    if not require_instrument(instr, f"set the frequency on channel {channel}"):
        return None

    frequency = clamp_frequency(frequency, waveform)
    try:
        instr.write(f'C{channel}:BSWV FRQ,{frequency}')
        time.sleep(COMMAND_SETTLE_S)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} frequency set to {frequency} Hz.")
        print(f"  New settings: {new_status.strip()}")
        return frequency
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set frequency on channel {channel}: {describe_visa_error(e)}")
        return None


def set_amplitude(instr, amplitude, channel=1):
    """Set peak-to-peak amplitude in Vpp (clamped to 2 mVpp – 20 Vpp)."""
    if not require_instrument(instr, f"set the amplitude on channel {channel}"):
        return None

    amplitude = clamp_amplitude(amplitude)
    try:
        instr.write(f'C{channel}:BSWV AMP,{amplitude}')
        time.sleep(COMMAND_SETTLE_S)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} amplitude set to {amplitude} Vpp.")
        print(f"  New settings: {new_status.strip()}")
        return amplitude
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set amplitude on channel {channel}: {describe_visa_error(e)}")
        return None


def set_offset(instr, offset, amplitude=0.0, channel=1):
    """Set DC offset in Volts (clamped so peaks stay within the ±10 V rail)."""
    if not require_instrument(instr, f"set the offset on channel {channel}"):
        return None

    offset = clamp_offset(offset, amplitude)
    try:
        instr.write(f'C{channel}:BSWV OFST,{offset}')
        time.sleep(COMMAND_SETTLE_S)
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"Channel {channel} offset set to {offset} V.")
        print(f"  New settings: {new_status.strip()}")
        return offset
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not set offset on channel {channel}: {describe_visa_error(e)}")
        return None


def configure_channel(instr, waveform="sine", frequency=1000.0,
                      amplitude=1.0, offset=0.0, channel=1):
    """
    Set waveform type, frequency, amplitude, and offset in one call.
    Returns a dict of the values actually applied (None for any failed step).

    Deliberately does NOT turn the output on and does NOT return a
    "channel output" key -- unlike the older signal_generator_control.py's
    configure_channel(), which does both. Configuring a channel and
    enabling its output are kept as two separate, single-responsibility
    calls here; see turn_on_output() in output.py.
    """
    if not require_instrument(instr, f"configure channel {channel}"):
        return {"waveform": None, "frequency": None, "amplitude": None, "offset": None}

    applied_waveform  = set_waveform(instr, waveform, channel=channel)
    applied_frequency = set_frequency(instr, frequency, channel=channel,
                                      waveform=applied_waveform or waveform)
    applied_amplitude = set_amplitude(instr, amplitude, channel=channel)
    applied_offset    = set_offset(instr, offset,
                                   amplitude=applied_amplitude or amplitude,
                                   channel=channel)
    return {
        "waveform":  applied_waveform,
        "frequency": applied_frequency,
        "amplitude": applied_amplitude,
        "offset":    applied_offset,
    }