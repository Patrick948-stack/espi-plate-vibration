"""
test_syst_err_isolated.py
Author: Patrick Mulikuza

Purpose: isolate ONE command (SYST:ERR?) and send it completely by itself,
with nothing before it and nothing after it. This is the "control group"
version of a test.

Why bother? Because in the full debug script, SYST:ERR? was sent right
after other queries had already succeeded. If SYST:ERR? still times out
here, when it's the very first and only thing sent, that tells me the
problem is with THIS COMMAND SPECIFICALLY, not with leftover state from
whatever query ran before it. If it magically works here but not in the
full script, that would point the other way, toward some kind of sequence
or timing problem instead.

Run it with:
    python test_syst_err_isolated.py
"""

import pyvisa

from signal_generator_control import (
    find_instruments,
    connect_instrument,
    close_connection,
)


def main():
    # '@py' forces the pure-Python pyvisa-py backend, which correctly finds
    # this instrument's real USB SCPI resource (USB0::...::INSTR) instead of
    # whatever the default (NI-VISA) backend decides to report.
    print("Opening ResourceManager with the '@py' backend...")
    rm = pyvisa.ResourceManager('@py')

    # find_instruments() (from signal_generator_control) scans for VISA
    # resources and prints what it finds.
    instrs = find_instruments(rm)
    if instrs is None:
        return 1

    # I'm not going to blindly grab instrs[0] here, because that's the exact
    # assumption that caused the original bug (grabbing an ASRL/serial
    # resource instead of the real instrument). Instead I filter for the one
    # that starts with "USB", since that's the real instrument channel.
    usb_indices = [i for i, addr in enumerate(instrs) if addr.startswith("USB")]
    if not usb_indices:
        print("No USB VISA resource found. Is the signal generator on and plugged in?")
        return 1

    # connect_instrument() (from signal_generator_control) opens the resource
    # and sets read/write termination characters and a default timeout for us.
    instr = connect_instrument(rm, instrs, index=usb_indices[0])
    if instr is None:
        return 1

    # Override the default timeout with a short one on purpose. If SYST:ERR?
    # is really going to fail, I don't want to sit here for 10+ seconds to
    # find that out every time I re-run this test while isolating the problem.
    instr.timeout = 5000

    print("Connection opened. Sending ONLY SYST:ERR? now, nothing else before it.")

    # This is the actual test. instr.query() both writes the command AND
    # waits for a response, all in one call. There is nothing else sent
    # to the instrument before this line in this whole script, on purpose.
    try:
        response = instr.query('SYST:ERR?')
        print(f"SUCCESS: instrument replied with: {response.strip()}")
    except pyvisa.VisaIOError as e:
        # I'm catching specifically VisaIOError (not a generic Exception)
        # because that's the exact error type PyVISA raises for
        # communication problems like timeouts. Catching the specific
        # error type here, instead of a broad "except Exception", makes
        # it obvious in my own code what kind of failure I'm expecting
        # and handling.
        print(f"FAILED: {e.abbreviation}: {e.description}")
        print("This means SYST:ERR? timed out even with nothing else sent first.")
        print("That points to the command itself, not to leftover state from a prior query.")

    # close_connection() (from signal_generator_control) closes the session
    # and prints confirmation, so the USB resource isn't left open and
    # unavailable if I want to run this test again right away.
    close_connection(instr)
    return 0


# This check means "only run main() if this file is being run directly,
# not if it's imported into another script." Standard Python habit for
# any script meant to be run on its own.
if __name__ == "__main__":
    raise SystemExit(main())
