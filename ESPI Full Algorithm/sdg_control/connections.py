"""
connection.py
Finding, opening, and closing VISA sessions with the SDG1015.
"""

import pyvisa

DEFAULT_TIMEOUT_MS = 10000


def find_instruments(rm):
    """List all VISA-visible instruments. Returns a tuple of addresses, or None."""
    instrs = rm.list_resources()
    if len(instrs) == 0:
        print("[ERROR] No instruments found. Check USB connection and driver.")
        return None
    print(f"Found {len(instrs)} instrument(s):")
    for i, addr in enumerate(instrs):
        print(f"  [{i}] {addr}")
    return instrs


def connect_instrument(rm, instrs, index=0):
    """Open a session with the instrument at the given index."""
    instr = rm.open_resource(instrs[index])
    instr.timeout = DEFAULT_TIMEOUT_MS
    instr.read_termination = '\n'
    instr.write_termination = '\n'
    print(f"Opened connection to: {instrs[index]}")
    return instr


def open_connection(index=0):
    """
    Convenience wrapper: create a resource manager, scan, and open the
    instrument at `index`. Returns None if nothing is connected.
    """
    rm = pyvisa.ResourceManager()
    instrs = find_instruments(rm)
    if instrs is None:
        return None
    return connect_instrument(rm, instrs, index=index)


def close_connection(instr):
    """Close the VISA session. Always call this when finished."""
    instr.close()
    print("Connection closed.")