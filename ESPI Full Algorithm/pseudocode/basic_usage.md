# examples/basic_usage.py — Plain-Language Pseudocode

## What this file is for

This is a short demonstration script showing the minimum code needed to
drive the signal generator through the `sdg_control` package. It is meant to
be read as a learning example, not used as part of a real experiment.

## How to run it

```
python examples/basic_usage.py
```

Run from the project root folder, not from inside `examples/`.

## Step-by-step pseudocode

```
add the project's root folder to Python's import search path
    # necessary because this file lives inside the examples/ subfolder,
    # one level below where sdg_control/ actually is

import open_connection, close_connection, get_identity, turn_on_output,
       turn_off_output, configure_channel  from sdg_control

function main():
    instr = open_connection()
    if instr is nothing: stop (no signal generator found)

    get_identity(instr)   # prints manufacturer, model, serial number

    result = configure_channel(instr, waveform="sine", frequency=1000,
                                amplitude=3.0, offset=0.0, channel=1)
    print what was actually applied

    turn_on_output(instr, channel=1)
    wait for the user to press Enter
    turn_off_output(instr, channel=1)
    close_connection(instr)
```

## A problem worth flagging

This script imports everything it needs from the `sdg_control` package.
As documented in `sdg_control_package.md`, that package currently has a
broken import (`__init__.py` looks for a file named `connection.py`, but the
folder actually contains `connections.py`) and an empty `output.py` file
that is missing the functions `__init__.py` expects to find in it. Because
of this, running `examples/basic_usage.py` as written will currently fail
with an import error before it ever reaches the signal generator. The same
four-step pattern (connect, configure, turn on, turn off, close) works today
if the functions are imported from `signal_generator_control.py` instead.
