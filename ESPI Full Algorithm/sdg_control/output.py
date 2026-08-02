"""
output.py
Turn the signal generator's physical output on and off.
"""

import time
import pyvisa

from .constants import OUTPUT_SETTLE_S
from .errors import describe_visa_error, require_instrument


def turn_on_output(instr, channel=1):
    """
    Switch the physical output on a channel ON.

    Waits OUTPUT_SETTLE_S after sending the command before querying the
    instrument to confirm, since the relay that switches the output
    physically takes a moment to close.

    Returns:
        int: The channel number, on success.
        None: If instr is None or a communication error occurred.
    """
    if not require_instrument(instr, f"turn on channel {channel}"):
        return None

    try:
        instr.write(f'C{channel}:OUTP ON')
        time.sleep(OUTPUT_SETTLE_S)
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return channel
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn on channel {channel}: {describe_visa_error(e)}")
        return None


def turn_off_output(instr, channel=1):
    """
    Switch the physical output on a channel OFF.

    Waits OUTPUT_SETTLE_S after sending the command before querying the
    instrument to confirm, since the relay that switches the output
    physically takes a moment to open.

    Returns:
        int: The channel number, on success.
        None: If instr is None or a communication error occurred.
    """
    if not require_instrument(instr, f"turn off channel {channel}"):
        return None

    try:
        instr.write(f'C{channel}:OUTP OFF')
        time.sleep(OUTPUT_SETTLE_S)
        status = instr.query(f'C{channel}:OUTP?')
        print(f"Channel {channel} output is now: {status.strip()}")
        return channel
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not turn off channel {channel}: {describe_visa_error(e)}")
        return None
