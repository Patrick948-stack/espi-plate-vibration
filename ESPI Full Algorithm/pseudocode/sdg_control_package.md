# sdg_control/ — Plain-Language Pseudocode

## What this package is for

`sdg_control` is a folder (Python calls this a "package") that splits
`signal_generator_control.py` into five smaller files, one per responsibility,
instead of one large file. The logic is identical to
`signal_generator_control.py` — see that pseudocode file for the detailed
step-by-step behavior of each function. This document explains how the split
is organized and how the pieces fit together.

## Beginner glossary

- **Package** — a folder containing an `__init__.py` file, which lets Python
  treat the folder as a single importable unit (`import sdg_control`).
- **`__init__.py`** — the file that runs automatically when a package is
  imported. Its job here is to gather functions from the other files in the
  folder and make them available directly from `sdg_control`, so a caller can
  write `from sdg_control import open_connection` instead of
  `from sdg_control.connections import open_connection`.

## How the five files divide the work

```
sdg_control/
    __init__.py     — gathers everything below into one importable namespace
    connections.py  — find_instruments, connect_instrument,
                       open_connection, close_connection
    status.py       — get_identity, get_output_status, get_wave_status
    output.py       — meant to hold turn_on_output, turn_off_output
    waveform.py     — set_waveform, set_frequency, set_amplitude,
                       set_offset, configure_channel
    limits.py       — clamp_frequency, clamp_amplitude, clamp_offset
                       (pure math, no hardware — easy to unit test alone)
```

Pseudocode for what `__init__.py` does on import:

```
import connect/close functions from connections.py
import identity/status functions from status.py
import output on/off functions from output.py
import waveform setters and configure_channel from waveform.py
import clamp functions from limits.py
list every one of the above names in __all__, so
    "from sdg_control import *" exposes exactly this set
```

`waveform.py` imports its clamp functions from `limits.py`, so setting a
frequency, amplitude, or offset always goes through the same safety clamps
described in the `signal_generator_control.py` pseudocode.

## A problem worth flagging

While reading these files to write this document, two issues turned up that
would stop the package from importing successfully:

1. `__init__.py` contains the line `from .connection import (...)` (singular
   "connection"), but the file in this folder is actually named
   `connections.py` (plural). Python will not find a module named
   `connection`, so `import sdg_control` currently fails with a
   `ModuleNotFoundError`.
2. `output.py` is completely empty (0 bytes), but `__init__.py` tries to
   import `turn_on_output` and `turn_off_output` from it. Even after fixing
   issue 1, the import would still fail because those two functions do not
   exist anywhere in this file.

Because of these two problems, `import sdg_control` (and therefore
`examples/basic_usage.py`, which relies on it) will not currently run. The
top-level `signal_generator_control.py` file does not have this problem — it
contains all the same functions in one working file — so any script that
needs the signal generator today should import from
`signal_generator_control.py` instead of `sdg_control` until these two files
are fixed.
