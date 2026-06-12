"""
basic_usage.py
Minimal demonstration of the sdg_control package.
Run from the project root:  python examples/basic_usage.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdg_control import (
    open_connection,
    close_connection,
    get_identity,
    turn_on_output,
    turn_off_output,
    configure_channel,
)


def main():
    instr = open_connection(index=0)
    if instr is None:
        return

    get_identity(instr)

    result = configure_channel(instr,
                               waveform="sine",
                               frequency=1000,   # 1 kHz
                               amplitude=3.0,    # 3 Vpp
                               offset=0.0,
                               channel=1)
    print(f"\nApplied settings: {result}")

    turn_on_output(instr, channel=1)
    input("Press Enter to turn output off and disconnect...")
    turn_off_output(instr, channel=1)
    close_connection(instr)


if __name__ == "__main__":
    main()