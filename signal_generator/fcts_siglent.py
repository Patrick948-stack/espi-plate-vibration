"""
fcts_siglent.py
Author: Patrick Mulikuza

PyVISA-based control library for the Siglent SDG1015 function/arbitrary waveform generator.

This module provides functions to connect to the instrument over USB, control its output
channel (waveform type, frequency, amplitude, DC offset), and query its current state —
all via SCPI commands sent through the PyVISA interface.

Hardware limits are enforced automatically through clamping functions before any command
is sent to the instrument, preventing out-of-range values from causing errors or damage.

Key variables:
    rm = pyvisa.ResourceManager()
    instrs = find_instruments(rm)
    instr = select_instrument(rm, instrs)
    set_frequency(instr, 1000, channel=1, waveform="sine")
    set_amplitude(instr, 5.0, channel=1)
    instr.close()

Dependencies:
    pyvisa  — VISA communication layer (pip install pyvisa)
    time    — standard library, used for hardware settling delays
"""

import pyvisa
import time

# --- Clamping functions ---
# These enforce hardware limits by snapping out-of-range values to the nearest allowed limit
# instead of rejecting the input entirely.

def clamp_frequency(frequency, waveform="sine"):
    """
    Clamps a frequency value to the allowed range for a given waveform type on the SDG1015.

    Parameters:
        frequency (float): Desired frequency in Hz. Any positive number is accepted;
                           out-of-range values will be automatically adjusted.
        waveform (str):    Type of waveform currently set on the instrument.
                           Options: "sine", "square", "ramp", "pulse", "arb", "noise"
                           Default is "sine". Change this to match the active waveform
                           so the correct frequency ceiling is applied.

    Returns:
        float: The clamped frequency in Hz, guaranteed to be within hardware limits.

    Logic:
        Each waveform type has a different maximum frequency due to hardware bandwidth limits.
        The function looks up the (min, max) pair for the given waveform, then uses
        max(min_f, min(frequency, max_f)) to snap the value into range in one line.
        If the waveform type is not in the dictionary, it defaults to sine limits.
    """
    limits = {
        "sine":   (1e-6, 15e6),   # 1 uHz to 15 MHz
        "square": (1e-6, 15e6),   # 1 uHz to 15 MHz
        "ramp":   (1e-6, 3e5),    # 1 uHz to 300 kHz
        "pulse":  (5e-4, 5e6),    # 500 uHz to 5 MHz
        "arb":    (1e-6, 5e6),    # 1 uHz to 5 MHz
        "noise":  (1e-6, 50e6),   # 1 uHz to 50 MHz
    }
    min_f, max_f = limits.get(waveform.lower(), (1e-6, 15e6)) # look up in the limit dictionary, using the waveform key, the corresponding value (a tuple of two elements). Assign min_f to the first element of the tuple and max_f to the second one. If the key (waveform) isn't found in the dictionary, then default to the limits of the sine wave. 

    # max(min_f, ...) raises values that are too low; min(..., max_f) lowers values that are too high
    # This is the line that clamps the value, forcing frequency to stay within the range [min_f, max_f]
    clamped = max(min_f, min(frequency, max_f))

    if clamped != frequency:
        print(f"Frequency {frequency} Hz out of range for {waveform}. Clamped to {clamped} Hz.")
    return clamped


def clamp_amplitude(amplitude):
    """
    Clamps an amplitude value to the SDG1015's supported output range.

    Parameters:
        amplitude (float): Desired peak-to-peak amplitude in Volts (Vpp).
                           To change the range, update MIN_AMP or MAX_AMP below.

    Returns:
        float: The clamped amplitude in Vpp, between 2 mVpp and 20 Vpp.

    Logic:
        The SDG1015 supports a minimum of 2 mVpp (0.002 V) and a maximum of 20 Vpp.
        Values outside this range are snapped to the nearest limit.
    """
    MIN_AMP = 0.002   # 2 mVpp — smallest signal the instrument can output
    MAX_AMP = 20.0    # 20 Vpp — largest signal before hardware damage risk

    clamped = max(MIN_AMP, min(amplitude, MAX_AMP))

    if clamped != amplitude:
        print(f"Amplitude {amplitude} Vpp out of range. Clamped to {clamped} Vpp.")
    return clamped


def clamp_offset(offset, amplitude=0):
    """
    Clamps a DC offset voltage to a safe range given the current amplitude setting.

    Parameters:
        offset (float):    Desired DC offset in Volts. Can be positive or negative.
        amplitude (float): Current peak-to-peak amplitude in Vpp. Default is 0.
                           Must be passed in so the rail constraint can be checked.
                           To change the output rail limit, update the 10.0 constant below.

    Returns:
        float: The clamped offset in Volts, safe for the current amplitude setting.

    Logic:
        The instrument's output cannot exceed its internal voltage rail (~10V).
        The signal swings from (offset - amplitude/2) to (offset + amplitude/2).
        So the maximum safe offset is:  10V - |amplitude / 2|
        Example: if amplitude = 4 Vpp, the signal swings ±2V around the offset.
                 The offset must stay within ±8V so the peak never exceeds 10V.
        The offset is then clamped symmetrically between -max_offset and +max_offset.
    """
    # Subtract half the amplitude swing from the rail to get the safe offset window
    # the line ensure that the maximum offset is never negative
    max_offset = max(0.0, 10.0 - abs(amplitude / 2)) 

    # Clamp offset to [-max_offset, +max_offset]
    clamped = max(-max_offset, min(offset, max_offset))

    if clamped != offset:
        print(f"Offset {offset} V out of range. Clamped to {clamped} V.")
    return clamped


# --- Instrument functions ---

def find_instruments(rm):
    """
    Scans for all instruments connected to the computer and returns them as a tuple.

    Parameters:
        rm: A pyvisa.ResourceManager object. This is the entry point PyVISA uses
            to search for connected devices. Create it with: rm = pyvisa.ResourceManager()

    Returns:
        tuple: A tuple of VISA resource strings, one per detected instrument.
               Example: ('USB0::62701::60986::SDG10GAC3R0028::0::INSTR',)
               Returns None if no instruments are found, so the caller can exit early.

    Logic:
        rm.list_resources() queries all VISA backends (USB, GPIB, TCPIP, etc.)
        and returns whatever is currently connected. If the tuple is empty,
        the function prints a message and returns None instead of an empty tuple,
        so callers can check "if instrs is None" to detect the no-instrument case.
    """
    # Scan all connected VISA resources (USB, GPIB, TCPIP, etc.)
    instrs = rm.list_resources()

    if len(instrs) == 0:
        print("Sorry, no instrument found!")
        return None  # Signal to caller that nothing was found — lets main() exit cleanly

    print("Connected instrument(s):")
    print(instrs)
    return instrs


def select_instrument(rm, instrs):
    """
    Prompts the user to choose an instrument from the detected list, opens it, and configures it.

    Parameters:
        rm:     A pyvisa.ResourceManager object (same one passed to find_instruments).
        instrs: The tuple returned by find_instruments — the list of available instruments.

    Returns:
        instr: An open PyVISA resource object representing the selected instrument.
               This object is used by all other functions to send and receive commands.

    Logic:
        The user picks a number (0-indexed) corresponding to a position in the instrs tuple.
        rm.open_resource() opens a communication session with that instrument.
        The three lines after that configure how messages are sent and received:
          - timeout: how long PyVISA waits for a response before giving up (in milliseconds)
          - read_termination: the character that signals "end of message" coming FROM the instrument
          - write_termination: the character appended to every command sent TO the instrument
    """
    n = int(input("Pick a number starting from 0 to number of instruments minus 1: "))
    instr = rm.open_resource(instrs[n])

    instr.timeout = 10000          # Wait up to 10 seconds for instrument response before timing out
    instr.read_termination = '\n'  # Tell PyVISA a newline marks the end of a response from the instrument
    instr.write_termination = '\n' # Append a newline to every command sent so instrument knows it's complete

    return instr


def get_identity(instr):
    """
    Queries and prints the instrument's identity string.

    Parameters:
        instr: Open PyVISA resource object returned by select_instrument.

    Returns:
        Nothing. Prints the identity directly.

    Logic:
        *IDN? is a universal SCPI command supported by all IEEE 488.2-compliant instruments.
        The response format is: Manufacturer, Model, Serial Number, Firmware Version
        Example: SDG,SDG1025,SDG10GAC3R0028,1.01.01.39R5
    """
    print("Instrument identity:")
    print(instr.query('*IDN?'))


def get_output_status(instr, channel=1):
    """
    Queries and prints whether the output on a given channel is ON or OFF.

    Parameters:
        instr:      Open PyVISA resource object.
        channel (int): Channel number to query. Default is 1 (C1).
                       Change to 2 for the second output channel if available.

    Returns:
        Nothing. Prints the status directly.
    """
    status = instr.query(f'C{channel}:OUTP?')
    print(f"Signal Generator Status: {status}")


def turn_on_output(instr, channel=1):
    """
    Turns on the output for a given channel.

    Parameters:
        instr:         Open PyVISA resource object.
        channel (int): Channel to turn on. Default is 1. Change to 2 for channel 2.

    Returns:
        Nothing. Prints the updated output status after turning on.

    Logic:
        After sending the ON command, the code waits 0.5 seconds before querying
        the status. This pause is necessary because the instrument needs time to
        physically switch the output relay before it can report the new state.
        Without the sleep, the query fires before the change is applied.
    """
    try:
        instr.write(f'C{channel}:OUTP ON')
        time.sleep(0.5)  # Wait for instrument to apply the change before querying
        changed_status = instr.query(f'C{channel}:OUTP?')
        print(f"Changed Signal Generator Status: {changed_status.strip()}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")


def get_wave_status(instr, channel=1):
    """
    Queries and prints all waveform parameters for a given channel.

    Parameters:
        instr:         Open PyVISA resource object.
        channel (int): Channel to query. Default is 1.

    Returns:
        Nothing. Prints the full waveform parameter string directly.

    Logic:
        BSWV? returns a single string with all basic waveform settings including:
        waveform type (WVTP), frequency (FRQ), period (PERI), amplitude (AMP),
        offset (OFST), high level (HLEV), low level (LLEV), phase (PHSE),
        and duty cycle (DUTY) for square waves.
    """
    wave_status = instr.query(f'C{channel}:BSWV?')
    print("\n--- Wave Status ---\n")
    print(wave_status)


def set_waveform(instr, channel=1):
    """
    Prompts the user to choose a waveform type and sets it on the given channel.

    Parameters:
        instr:         Open PyVISA resource object.
        channel (int): Channel to configure. Default is 1.

    Returns:
        str: The chosen waveform key in lowercase (e.g. "square", "sine"), so the
             caller can pass it to set_frequency for the correct frequency clamping.
             Returns None if a VISA error occurs.

    Logic:
        Presents a numbered menu of available waveform types. The user picks a number,
        the corresponding SCPI token is sent via BSWV WVTP. Success is verified by
        checking that the instrument echoes back the expected WVTP token.
    """
    waveform_options = {
        "1": ("SINE",   "Sine wave"),
        "2": ("SQUARE", "Square wave"),
        "3": ("RAMP",   "Ramp / Triangle wave"),
        "4": ("PULSE",  "Pulse wave"),
        "5": ("NOISE",  "Noise (white noise)"),
        "6": ("ARB",    "Arbitrary waveform"),
        "7": ("DC",     "DC voltage"),
    }

    print("\nAvailable waveform types: \n")
    for key, (token, label) in waveform_options.items():
        print(f"  {key}. {label}")

    choice = input("Enter the number of your desired waveform: ").strip()

    if choice not in waveform_options:
        print(f"Invalid choice '{choice}'. Waveform was set to a sine wave.")
        choice = "1"

    token, label = waveform_options[choice]

    try:
        instr.write(f'C{channel}:BSWV WVTP,{token}')
        time.sleep(0.2)  # Brief pause before querying so instrument has time to apply the change
        new_status = instr.query(f'C{channel}:BSWV?')

        if f'WVTP,{token}' in new_status:
            print(f'\n----- Success! Waveform changed to {label} -----\n')
            print(f"New wave settings: {new_status}")
        else:
            print(f'Failed to update waveform to {label}!')
            print(f"Device reported: {new_status}")

        return token.lower()

    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")
        return None


def set_frequency(instr, frequency, channel=1, waveform="sine"):
    """
    Sets the output frequency on a given channel after clamping to hardware limits.

    Parameters:
        instr:           Open PyVISA resource object.
        frequency (float): Desired frequency in Hz. Out-of-range values are clamped,
                           not rejected. To allow a wider range, update clamp_frequency().
        channel (int):   Channel to configure. Default is 1.
        waveform (str):  The active waveform type — needed to apply the correct frequency
                         ceiling. Must match what is set on the instrument.
                         Options: "sine", "square", "ramp", "pulse", "arb", "noise"
                         Default is "sine". Change this if you switch waveform types.

    Returns:
        Nothing. Prints success message and full waveform status after applying change.

    Logic:
        clamp_frequency() is called first to silently enforce hardware limits.
        Success is determined by whether a VisaIOError is raised — NOT by parsing
        the response string. The instrument appends units to values (e.g. "2000HZ")
        which would break any string comparison using the raw float (e.g. "2000.0").
    """
    frequency = clamp_frequency(frequency, waveform)  # Enforce hardware limits before sending
    try:
        instr.write(f'C{channel}:BSWV FRQ,{frequency}')
        time.sleep(0.2)  # Pause before querying — instrument needs time to apply change
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"\n--- 🎖️ Success! The frequency has been changed to {frequency} Hz. \n")
        print(f"New wave settings: {new_status}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")


def set_amplitude(instr, amplitude, channel=1):
    """
    Sets the peak-to-peak output amplitude in Vpp on a given channel.

    Parameters:
        instr:            Open PyVISA resource object.
        amplitude (float): Desired amplitude in Volts peak-to-peak (Vpp).
                           Out-of-range values are clamped to [0.002, 20.0] Vpp.
                           To change the limits, update clamp_amplitude().
        channel (int):    Channel to configure. Default is 1.

    Returns:
        Nothing. Prints success message and full waveform status after applying change.

    Logic:
        Same pattern as set_frequency — clamp first, write, short sleep, then query.
        Success is inferred from no exception being raised, not from string matching,
        because the instrument appends "V" to amplitude values in its response.
    """
    amplitude = clamp_amplitude(amplitude)  # Enforce hardware limits before sending
    try:
        instr.write(f'C{channel}:BSWV AMP,{amplitude}')
        time.sleep(0.2)  # Pause before querying — instrument needs time to apply change
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"\n---🎖️Success! The amplitude has been changed to {amplitude} Vpp. \n")
        print(f"New wave settings: {new_status}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")


def set_offset(instr, ofs_volt, amplitude=0, channel=1):
    """
    Sets the DC offset voltage on a given channel.

    Parameters:
        instr:           Open PyVISA resource object.
        ofs_volt (float): Desired DC offset in Volts. Can be positive or negative.
                          Out-of-range values are clamped based on the current amplitude.
                          To change the rail limit, update the 10.0 constant in clamp_offset().
        amplitude (float): The current amplitude setting in Vpp. Default is 0.
                           Pass the actual amplitude so the clamp can enforce the rail constraint:
                           |amplitude/2| + |offset| must not exceed 10V.
                           If you omit this, the clamp assumes 0 Vpp amplitude (unsafe for large signals).
        channel (int):   Channel to configure. Default is 1.

    Returns:
        Nothing. Prints success message and full waveform status after applying change.
    """
    ofs_volt = clamp_offset(ofs_volt, amplitude)  # Enforce rail constraint before sending
    try:
        instr.write(f'C{channel}:BSWV OFST,{ofs_volt}')
        time.sleep(0.2)  # Pause before querying — instrument needs time to apply change
        new_status = instr.query(f'C{channel}:BSWV?')
        print(f"\n---🎖️Success! The offset voltage has been changed to {ofs_volt} V. \n")
        print(f"New wave settings: {new_status}")
    except pyvisa.VisaIOError as e:
        print(f"Error type: {e.error_code}")
        print(f"Error Message: {e.description}")


def main():
    """
    Entry point. Connects to the instrument and runs through a full configuration sequence:
    turn on output, prompt user to select a waveform type, then set frequency, amplitude, and offset.
    """
    rm = pyvisa.ResourceManager()  # Create the VISA resource manager — entry point for all communication
    instrs = find_instruments(rm)
    if instrs is None:
        return  # Exit early — no point continuing without an instrument

    instr = select_instrument(rm, instrs)
    get_identity(instr)
    get_output_status(instr)
    turn_on_output(instr)
    get_wave_status(instr)
    chosen_waveform = set_waveform(instr)

    frequency_value = float(input("Enter your desired frequency in Hz: "))
    set_frequency(instr, frequency_value, channel=1, waveform=chosen_waveform or "sine")

    amplitude_value = float(input("Enter your desired amplitude in Vpp: "))
    set_amplitude(instr, amplitude_value, channel=1)

    offset_value = float(input("Enter your desired offset voltage in V: "))
    # Pass amplitude_value into set_offset so the clamp can enforce the output rail constraint
    set_offset(instr, offset_value, amplitude=amplitude_value, channel=1)

    instr.close()  # Always close the connection when done


main()
