"""
status.py
Read-only queries — these never change instrument settings.
"""

import pyvisa

from .errors import describe_visa_error, require_instrument


def get_identity(instr):
    """Query *IDN? and return the identity string."""
    if not require_instrument(instr, "read the instrument identity"):
        return None

    try:
        identity = instr.query('*IDN?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read instrument identity: {describe_visa_error(e)}")
        return None

    print(f"Instrument identity: {identity.strip()}")
    return identity.strip()


def get_output_status(instr, channel=1):
    """Return the raw ON/OFF status string for a channel."""
    if not require_instrument(instr, f"read the output status for channel {channel}"):
        return None

    try:
        status = instr.query(f'C{channel}:OUTP?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read channel {channel} output status: "
              f"{describe_visa_error(e)}")
        return None

    print(f"Channel {channel} output status: {status.strip()}")
    return status.strip()


def get_wave_status(instr, channel=1):
    """Return the full waveform-settings string for a channel."""
    if not require_instrument(instr, f"read the waveform status for channel {channel}"):
        return None

    try:
        wave_status = instr.query(f'C{channel}:BSWV?')
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not read channel {channel} waveform status: "
              f"{describe_visa_error(e)}")
        return None

    print(f"\n--- Channel {channel} waveform status ---")
    print(wave_status.strip())
    return wave_status.strip()
