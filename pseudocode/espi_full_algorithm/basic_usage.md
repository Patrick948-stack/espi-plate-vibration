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

## History

An earlier version of the `sdg_control` package had a broken import
(`__init__.py` looked for a file named `connection.py`, but the folder
actually contained `connections.py`) and an empty `output.py` file, so
this script could not actually run yet. Both were fixed since; see
`sdg_control.md` for the package as it stands now.
