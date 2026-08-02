"""
errors.py
Shared error-diagnostics helpers used across sdg_control's modules.

Two kinds of mistake account for almost every crash reported from this
library:

  1. A VISA-level communication error -- cable unplugged, instrument busy,
     driver not installed correctly. pyvisa's own e.description is accurate
     but generic ("Timeout expired before operation completed."). It does
     not tell you what to actually go check. describe_visa_error() below
     translates the handful of error codes this lab's hardware actually
     produces into a specific, actionable sentence.

  2. Passing None as `instr` -- almost always because open_connection()
     returned None (no instrument found) and the result was used anyway
     without being checked first. Without a guard this turns into
     "AttributeError: 'NoneType' object has no attribute 'query'", which
     does not explain what actually went wrong. require_instrument() below
     catches this before it reaches pyvisa at all.
"""

# Maps pyvisa's error abbreviation (e.VisaIOError.abbreviation) to a sentence
# that says both what happened AND what to do about it. Any error code not
# listed here falls back to pyvisa's own e.description in describe_visa_error().
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
        "The instrument address is no longer valid -- the list of connected "
        "devices likely changed between finding it and using it. Call "
        "open_connection() again to get a fresh address."
    ),
}


def describe_visa_error(e):
    """
    Turn a pyvisa.VisaIOError into a specific, actionable sentence.

    Looks up the error's abbreviation (e.g. "VI_ERROR_TMO") in
    _VISA_ERROR_HELP. Falls back to pyvisa's own e.description for any
    error code this lab's hardware hasn't been seen to raise, so nothing
    is ever hidden -- worst case you just get pyvisa's original message.
    """
    return _VISA_ERROR_HELP.get(e.abbreviation, e.description)


def require_instrument(instr, action):
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
    """
    if instr is None:
        print(f"[ERROR] Cannot {action} -- no instrument is connected.")
        print("  This usually means open_connection() returned None earlier "
              "(no instrument was found) and that result was used without "
              "being checked first.")
        print("  Call open_connection() again and confirm it does not "
              "return None before sending any commands.")
        return False
    return True
