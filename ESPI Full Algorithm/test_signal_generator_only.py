"""
test_signal_generator_only.py
Author: Patrick Mulikuza

A tiny standalone script for testing the signal generator connection by
itself, with no camera involved. Use this to check that pyvisa/pyvisa-py
can see the Siglent SDG1015 before troubleshooting the full pipeline.

HOW TO RUN
----------
    python3 test_signal_generator_only.py

WHAT IT DOES
------------
  1. Lists every VISA instrument pyvisa-py can currently see.
  2. Connects to the first one found.
  3. Prints its identity string (manufacturer, model, serial number).
  4. Sets a safe, quiet test signal: 1 kHz sine wave, 1 Vpp, 0 V offset.
  5. Turns the output on for 3 seconds, then turns it off.
  6. Disconnects cleanly.

If step 1 finds nothing, the problem is before Python even gets involved —
it's a USB/driver-level issue (see the "Signal generator setup" section in
README.md for Windows-specific driver steps).
"""

import time

import pyvisa

from signal_generator_control import (
    connect_instrument,
    get_identity,
    configure_channel,
    turn_off_output,
    close_connection,
)


def main():
    print("=" * 56)
    print("  Signal generator connection test")
    print("=" * 56)

    # ------------------------------------------------------------------
    # STEP 1 — list every VISA instrument currently visible
    # ------------------------------------------------------------------
    print("\n[1/5] Scanning for VISA instruments...")
    rm = pyvisa.ResourceManager("@py")
    addresses = rm.list_resources()

    if len(addresses) == 0:
        print("\n[FAILED] No VISA instruments found.")
        print("  This means pyvisa-py cannot see ANY USB instrument at all —")
        print("  Python and pyvisa are not the problem here. Check, in order:")
        print("    1. Is the signal generator powered on and the USB cable connected?")
        print("    2. (Windows) Has Zadig been used to bind a WinUSB driver to it?")
        print("    3. (Windows) Is 'pyusb' AND 'libusb-package' both installed?")
        print("    4. Try: python -c \"import usb.core; "
              "print(list(usb.core.find(find_all=True)))\"")
        print("       An empty list or a 'NoBackendError' here confirms the")
        print("       problem is at the USB driver level, not in this script.")
        return

    print(f"  Found {len(addresses)} instrument(s):")
    for i, addr in enumerate(addresses):
        print(f"    [{i}] {addr}")

    # ------------------------------------------------------------------
    # STEP 2 — connect to the first instrument found
    # ------------------------------------------------------------------
    print("\n[2/5] Connecting to instrument [0]...")
    instr = connect_instrument(rm, addresses, index=0)

    # ------------------------------------------------------------------
    # STEP 3 — identify it
    # ------------------------------------------------------------------
    print("\n[3/5] Requesting identity...")
    identity = get_identity(instr)
    print(f"  Identity: {identity}")

    # ------------------------------------------------------------------
    # STEP 4 — configure a safe, quiet test signal
    # ------------------------------------------------------------------
    print("\n[4/5] Configuring test signal: 1 kHz sine, 1 Vpp, 0 V offset...")
    configure_channel(
        instr,
        waveform="sine",
        frequency=1000.0,
        amplitude=1.0,
        offset=0.0,
        channel=1,
    )

    # ------------------------------------------------------------------
    # STEP 5 — leave the output on briefly, then turn it off and disconnect
    # ------------------------------------------------------------------
    print("\n[5/5] Output is ON for 3 seconds, then turning off...")
    time.sleep(3)
    turn_off_output(instr, channel=1)
    close_connection(instr)

    print("\nSUCCESS — the signal generator connected, responded, and")
    print("accepted commands correctly.")


if __name__ == "__main__":
    main()
