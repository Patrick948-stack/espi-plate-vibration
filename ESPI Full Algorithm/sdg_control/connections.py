"""
connection.py
Finding, opening, and closing VISA sessions with the SDG1015.
"""

import os

import pyvisa

DEFAULT_TIMEOUT_MS = 10000
_ON_WINDOWS = os.name == "nt"


def get_resource_manager():
    """
    Create a pyvisa ResourceManager, choosing the VISA backend for the
    current operating system.

    On Windows, tries the native VISA backend first (NI-VISA, if installed)
    and falls back to the pure-Python '@py' backend if that fails to start
    — most Windows machines only do the Zadig driver step and never install
    NI-VISA, so the native backend raises immediately with nothing to find.
    On macOS and Linux, always uses '@py' directly.

    Note: this only catches the native backend failing to start. It will
    not catch the native backend starting but reporting the instrument
    under the wrong resource address (see README.md "Signal generator
    setup" for the NI-VISA bug this project hit before) — that failure mode
    doesn't raise, so it can't be caught here. discover_instruments() below
    is what actually guards against it.
    """
    if _ON_WINDOWS:
        try:
            return pyvisa.ResourceManager()
        except Exception as e:
            print(f"[WARN] Native VISA backend unavailable ({e}); "
                  f"falling back to the '@py' backend.")
    return pyvisa.ResourceManager('@py')


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


def _prefer_usb_resources(instrs):
    """
    Narrow a list of VISA resource addresses down to the ones that look like
    a real USB instrument interface (they start with "USB"), or return the
    original list unchanged if none of them do.

    Some backends (NI-VISA in particular) have been seen reporting this
    project's signal generator under its serial interface instead of its
    real USB SCPI interface. Blindly taking whichever resource comes first
    can silently grab the wrong one; preferring "USB"-prefixed addresses
    avoids that.
    """
    usb_only = tuple(addr for addr in instrs if addr.startswith("USB"))
    return usb_only if usb_only else instrs


def discover_instruments():
    """
    Create a resource manager and scan for VISA instruments, retrying with
    the '@py' backend if the one get_resource_manager() picked didn't
    report anything that looks like the instrument's real USB interface.

    Returns:
        (rm, instrs) : instrs is narrowed to USB-looking addresses when at
                       least one was found, or None if nothing was found
                       even after a retry.
    """
    rm = get_resource_manager()
    instrs = find_instruments(rm)
    saw_usb = instrs is not None and any(addr.startswith("USB") for addr in instrs)

    if _ON_WINDOWS and not saw_usb:
        print("[WARN] No USB instrument resource found under the current "
              "backend; retrying with the '@py' backend before giving up.")
        rm = pyvisa.ResourceManager('@py')
        instrs = find_instruments(rm)

    if instrs is not None:
        instrs = _prefer_usb_resources(instrs)

    return rm, instrs


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
    rm, instrs = discover_instruments()
    if instrs is None:
        return None
    return connect_instrument(rm, instrs, index=index)


def close_connection(instr):
    """Close the VISA session. Always call this when finished."""
    instr.close()
    print("Connection closed.")