"""
connection.py
Finding, opening, and closing VISA sessions with the SDG1015.
"""

import os

import pyvisa

from .errors import describe_visa_error, require_instrument

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
    """
    Scan for all VISA-compatible instruments connected right now.

    Returns:
        tuple : One VISA address string per detected instrument.
        None  : If nothing was found, or the VISA backend itself failed to
                scan (a broken pyvisa/pyvisa-py install, not "nothing is
                plugged in").
    """
    try:
        instrs = rm.list_resources()
    except Exception as e:
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
            "-- an empty list or a 'NoBackendError' confirms the problem is "
            "at the USB driver level, not in this script (see README.md "
            "'Signal generator setup')."
        )

        print("[ERROR] No VISA instruments found.")
        print("  This does not necessarily mean Python or pyvisa are broken "
              "-- check, in order:")
        for i, step in enumerate(steps, start=1):
            print(f"    {i}. {step}")
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
    """
    Open a session with the instrument at the given index.

    Returns:
        instr : An open PyVISA resource object.
        None  : If instrs is empty, index is out of range, or the
                instrument could not be opened (e.g. it was unplugged
                between find_instruments() finding it and this call
                trying to open it).
    """
    if not instrs:
        print("[ERROR] Cannot connect -- no instrument addresses were given.")
        print("  Call find_instruments() first and check it did not return None.")
        return None

    if index < 0 or index >= len(instrs):
        print(f"[ERROR] index={index} is out of range -- only {len(instrs)} "
              f"instrument(s) were found (valid indices: 0 to {len(instrs) - 1}).")
        return None

    try:
        instr = rm.open_resource(instrs[index])
    except pyvisa.VisaIOError as e:
        print(f"[ERROR] Could not open a connection to {instrs[index]}: "
              f"{describe_visa_error(e)}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error opening {instrs[index]}: {e}")
        return None

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
    try:
        rm, instrs = discover_instruments()
    except Exception as e:
        print(f"[ERROR] Could not start a VISA resource manager: {e}")
        print("  Make sure both packages are installed: pip install pyvisa pyvisa-py")
        if _ON_WINDOWS:
            print("  On Windows, also make sure the Zadig driver step has been "
                  "done (see README.md 'Signal generator setup (Windows only)'), "
                  "or install NI-VISA instead: https://www.ni.com")
        return None

    if instrs is None:
        return None  # find_instruments() already printed a specific reason

    return connect_instrument(rm, instrs, index=index)


def close_connection(instr):
    """Close the VISA session. Always call this when finished."""
    if not require_instrument(instr, "close the connection"):
        return

    try:
        instr.close()
        print("Connection closed.")
    except pyvisa.VisaIOError as e:
        # Usually harmless -- the instrument was likely already disconnected
        # or powered off, so there is nothing left to close cleanly.
        print(f"[WARNING] Instrument did not close cleanly: {describe_visa_error(e)}")