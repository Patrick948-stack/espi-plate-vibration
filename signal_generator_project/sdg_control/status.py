"""
status.py
Read-only queries — these never change instrument settings.
"""


def get_identity(instr):
    """Query *IDN? and return the identity string."""
    identity = instr.query('*IDN?')
    print(f"Instrument identity: {identity.strip()}")
    return identity.strip()


def get_output_status(instr, channel=1):
    """Return the raw ON/OFF status string for a channel."""
    status = instr.query(f'C{channel}:OUTP?')
    print(f"Channel {channel} output status: {status.strip()}")
    return status.strip()


def get_wave_status(instr, channel=1):
    """Return the full waveform-settings string for a channel."""
    wave_status = instr.query(f'C{channel}:BSWV?')
    print(f"\n--- Channel {channel} waveform status ---")
    print(wave_status.strip())
    return wave_status.strip()