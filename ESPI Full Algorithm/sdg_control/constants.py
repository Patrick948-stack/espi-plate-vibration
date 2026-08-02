"""
constants.py
Hardware-level timing constants for the Siglent SDG1015 signal generator.

Both values are settling delays: time to wait after sending a command
before querying the instrument to confirm it actually took effect. Kept
in one place so waveform.py and output.py never drift out of sync with
each other by each defining their own copy.
"""

COMMAND_SETTLE_S = 0.2
"""
Time to wait after changing a waveform parameter (waveform type,
frequency, amplitude, offset) before querying the instrument to confirm.
The SDG1015 applies these changes electronically, with no moving parts,
so this only needs to cover firmware processing time.
"""

OUTPUT_SETTLE_S = 0.5
"""
Time to wait after turning output ON or OFF before querying the status.
Enabling/disabling output physically switches a relay, which takes
longer to settle than an electronic parameter change above.
"""
