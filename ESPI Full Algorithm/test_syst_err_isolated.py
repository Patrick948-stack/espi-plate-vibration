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
    discover_instruments,
    connect_instrument,
    close_connection,
)


def main():
    # discover_instruments() picks '@py' on macOS/Linux, and on Windows
    # tries the native VISA backend first. It also protects against the
    # exact bug that caused the original problem: NI-VISA reporting this
    # instrument under the wrong (ASRL/serial) resource address instead of
    # its real USB one. If that happens, it retries with '@py' instead of
    # trusting the wrong address (see signal_generator_control.py for why).
    rm, instrs = discover_instruments()
    if instrs is None:
        return 1

    # connect_instrument() (from signal_generator_control) opens the resource
    # and sets read/write termination characters and a default timeout for us.
    instr = connect_instrument(rm, instrs, index=0)
    if instr is None:
        return 1

    # Override the default timeout with a short one on purpose. If SYST:ERR?
    # is really going to fail, I don't want to sit here for 10+ seconds to
    # find that out every time I re-run this test while isolating the problem.
    instr.timeout = 5000

    print("Connected. Now sending just one command, SYST:ERR?, with nothing sent before it.")

    # This is the actual test. instr.query() both writes the command AND
    # waits for a response, all in one call. There is nothing else sent
    # to the instrument before this line in this whole script, on purpose.
    try:
        response = instr.query('SYST:ERR?')
        print(f"Success: the instrument replied with: {response.strip()}")
    except pyvisa.VisaIOError as e:
        # I'm catching specifically VisaIOError (not a generic Exception)
        # because that's the exact error type PyVISA raises for
        # communication problems like timeouts. Catching the specific
        # error type here, instead of a broad "except Exception", makes
        # it obvious in my own code what kind of failure I'm expecting
        # and handling.
        print(f"No reply: {e.abbreviation}: {e.description}")
        print("This means SYST:ERR? timed out even with nothing else sent first.")
        print("That means the problem is with this specific command, not something")
        print("left over from an earlier command.")

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
