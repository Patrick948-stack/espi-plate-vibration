"""
debug_signal_generator_response.py
Author: Patrick Mulikuza

PyVISA helper for debugging slow or timing-out Siglent signal generator
responses, AND for confirming that write commands (setting frequency,
waveform, amplitude) actually take effect and don't silently lag.

Run from the project folder with the virtual environment active:

    python debug_signal_generator_response.py
    python debug_signal_generator_response.py --trials 5
    python debug_signal_generator_response.py --skip-write-tests
    python debug_signal_generator_response.py --channel C2 --address USB0::...

What it does:
  1. Opens the VISA resource manager and lists connected instruments.
  2. Opens the first (or specified) instrument and prints its *IDN?.
  3. Times a set of safe, read-only SCPI queries, optionally repeated
     several times so you can see whether latency is consistent or
     intermittent.
  4. Unless --skip-write-tests is passed: saves the current waveform
     state, tests setting frequency / waveform type / amplitude, VERIFIES
     each change by reading it back, times both the write and the
     verifying query separately, then restores the original state.
  5. Prints a summary flagging any command that was slower than
     SLOW_THRESHOLD_MS.
"""

import argparse
import re
import time

import pyvisa

SLOW_THRESHOLD_MS = 500.0

READ_ONLY_QUERIES = [
    "*IDN?",
    "SYST:ERR?",
    "STAT:OPER?",
]


def describe_visa_error(e):
    try:
        return f"{e.abbreviation}: {e.description}"
    except Exception:
        return str(e)


# ---------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------

def timed_call(fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (elapsed_ms, result_or_None, error_or_None)."""
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    except pyvisa.VisaIOError as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return elapsed, None, describe_visa_error(exc)
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return elapsed, None, str(exc)
    elapsed = (time.perf_counter() - start) * 1000.0
    return elapsed, result, None


def measure_query(instr, command, trials, timing_log):
    """Run `command` `trials` times, print each attempt, log timings."""
    print(f"\nAsking the instrument: {command}")
    last_response = None
    for trial in range(1, trials + 1):
        elapsed, response, error = timed_call(instr.query, command)
        label = f"  attempt {trial}/{trials}" if trials > 1 else "  "
        if error:
            print(f"{label} no reply after {elapsed:.0f} ms: {error}")
            timing_log.append((command, elapsed, False))
        else:
            print(f"{label} replied in {elapsed:.0f} ms: {response.strip()}")
            timing_log.append((command, elapsed, True))
            last_response = response
    return last_response


def run_read_only_diagnostics(instr, trials, timing_log):
    print("\nStep: asking the instrument some safe, read-only questions...")
    for command in READ_ONLY_QUERIES:
        measure_query(instr, command, trials, timing_log)


# ---------------------------------------------------------------------
# Write-and-verify tests (frequency, waveform, amplitude)
# ---------------------------------------------------------------------

def parse_numeric_with_unit(value_str):
    """Turn a SCPI value like '1.000000e+03HZ' or '2V' into a float, unit-agnostic."""
    match = re.match(r"([-+0-9.eE]+)", value_str)
    if not match:
        raise ValueError(f"Could not parse numeric value from '{value_str}'")
    return float(match.group(1))


def parse_bswv_response(response):
    """
    Parse a Siglent BSWV query response into a dict.
    Example input:
      'C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,2V,OFST,0V,PHSE,0'
    Returns:
      {'WVTP': 'SINE', 'FRQ': '1000HZ', 'PERI': '0.001S', 'AMP': '2V', ...}
    """
    body = response.strip()
    if " " in body:
        body = body.split(" ", 1)[1]
    tokens = body.split(",")
    pairs = {}
    for i in range(0, len(tokens) - 1, 2):
        key = tokens[i].strip()
        value = tokens[i + 1].strip()
        pairs[key] = value
    return pairs


def set_and_verify(instr, channel, param_key, write_value, expect_value,
                    numeric=False, tolerance=0.01, timing_log=None):
    """
    Write one BSWV parameter, then query the state back and confirm the
    instrument actually applied it. Times the write and the verify
    query separately so you can tell which one is slow.
    """
    write_cmd = f"{channel}:BSWV {param_key},{write_value}"
    print(f"\nTrying to change a setting: {write_cmd}")
    write_elapsed, _, write_error = timed_call(instr.write, write_cmd)
    if write_error:
        print(f"  Could not send that command after {write_elapsed:.0f} ms: {write_error}")
        if timing_log is not None:
            timing_log.append((write_cmd, write_elapsed, False))
        return False
    print(f"  The instrument accepted the command in {write_elapsed:.0f} ms.")
    if timing_log is not None:
        timing_log.append((write_cmd, write_elapsed, True))

    verify_cmd = f"{channel}:BSWV?"
    verify_elapsed, response, verify_error = timed_call(instr.query, verify_cmd)
    if verify_error:
        print(f"  Could not check whether the change took effect (no reply after {verify_elapsed:.0f} ms): {verify_error}")
        if timing_log is not None:
            timing_log.append((verify_cmd, verify_elapsed, False))
        return False
    if timing_log is not None:
        timing_log.append((verify_cmd, verify_elapsed, True))

    parsed = parse_bswv_response(response)
    actual = parsed.get(param_key)
    if actual is None:
        print(f"  The instrument replied in {verify_elapsed:.0f} ms, but did not include a value for {param_key}.")
        return False

    if numeric:
        try:
            actual_val = parse_numeric_with_unit(actual)
            expect_val = parse_numeric_with_unit(expect_value)
            ok = abs(actual_val - expect_val) <= tolerance * max(abs(expect_val), 1.0)
        except ValueError:
            ok = False
    else:
        ok = actual.upper() == expect_value.upper()

    status = "correct" if ok else "does not match"
    print(f"  Checked in {verify_elapsed:.0f} ms: {param_key} is now {actual} ({status}, expected {expect_value}).")
    return ok


def run_write_tests(instr, channel, timing_log):
    print(f"\nStep: changing a few settings on channel {channel} and checking they actually took effect...")

    save_cmd = f"{channel}:BSWV?"
    elapsed, original_response, error = timed_call(instr.query, save_cmd)
    if error:
        print(f"Could not read the current waveform settings, so skipping the write tests: {error}")
        return
    timing_log.append((save_cmd, elapsed, True))
    original_response = original_response.strip()
    print(f"Saved the current settings so they can be restored afterward ({elapsed:.0f} ms): {original_response}")

    results = []
    results.append(set_and_verify(
        instr, channel, "WVTP", "SQUARE", "SQUARE", timing_log=timing_log))
    results.append(set_and_verify(
        instr, channel, "FRQ", "2000HZ", "2000HZ", numeric=True, timing_log=timing_log))
    results.append(set_and_verify(
        instr, channel, "AMP", "1V", "1V", numeric=True, timing_log=timing_log))

    print(f"\nRestoring the original settings: {original_response}")
    elapsed, _, error = timed_call(instr.write, original_response)
    if error:
        print(f"Could not restore the original settings after {elapsed:.0f} ms: {error}")
        print("  The signal generator may still be set to the test values above. You may")
        print("  need to set it back to your desired settings by hand.")
    else:
        print(f"  Restored in {elapsed:.0f} ms.")
    timing_log.append((f"{channel}:BSWV (restore)", elapsed, error is None))

    passed = sum(1 for r in results if r)
    print(f"\n{passed} out of {len(results)} write tests passed.")


# ---------------------------------------------------------------------
# Setup / main
# ---------------------------------------------------------------------

def connect(backend):
    if backend:
        print(f"Connecting to instruments using the '{backend}' backend...")
        return pyvisa.ResourceManager(backend)
    print("Connecting to instruments using your computer's default backend...")
    return pyvisa.ResourceManager()


def print_summary(timing_log):
    print("\nSummary")
    slow = [(cmd, ms) for cmd, ms, ok in timing_log if ok and ms > SLOW_THRESHOLD_MS]
    failed = [cmd for cmd, ms, ok in timing_log if not ok]

    if not slow and not failed:
        print(f"All {len(timing_log)} commands got a reply in under {SLOW_THRESHOLD_MS:.0f} ms. Nothing looks slow.")
        return

    if slow:
        print(f"These commands took longer than {SLOW_THRESHOLD_MS:.0f} ms to get a reply:")
        for cmd, ms in slow:
            print(f"  {ms:7.0f} ms  {cmd}")
    if failed:
        print("These commands never got a reply (they failed or timed out):")
        for cmd in failed:
            print(f"  no reply  {cmd}")


def main():
    parser = argparse.ArgumentParser(
        description="Debug slow signal generator response time, and test set/verify commands via PyVISA."
    )
    parser.add_argument("--backend", default="@py",
                         help="PyVISA backend string. Defaults to '@py' (pyvisa-py), which "
                              "reliably finds this instrument's USB0::...::INSTR resource on "
                              "Windows, macOS, and Linux. Pass '' to use the OS default "
                              "(e.g. NI-VISA) instead, or '@ni' to force NI-VISA explicitly.")
    parser.add_argument("--timeout", type=int, default=20000,
                         help="Instrument timeout in milliseconds. Default: 20000.")
    parser.add_argument("--address", default=None,
                         help="VISA resource string to open directly, skipping auto-detection.")
    parser.add_argument("--channel", default="C1",
                         help="Channel to run write tests on, e.g. C1 or C2. Default: C1.")
    parser.add_argument("--trials", type=int, default=1,
                         help="Repeat each read-only query this many times. Default: 1.")
    parser.add_argument("--skip-write-tests", action="store_true",
                         help="Only run read-only diagnostics; do not change instrument state.")
    args = parser.parse_args()

    print("Signal generator speed test")
    print("Checking how fast the signal generator replies, and whether changing its settings actually works.\n")

    try:
        rm = connect(args.backend)
    except Exception as exc:
        print(f"Could not start talking to instruments at all: {exc}")
        print("  Make sure pyvisa and a backend driver are installed.")
        print("  Example: pip install pyvisa pyvisa-py libusb-package")
        return 1

    try:
        backend_path = rm.visalib.library_path
    except Exception:
        backend_path = "unknown"
    print(f"Using this VISA backend: {backend_path}")

    if args.address:
        address = args.address
    else:
        try:
            start = time.perf_counter()
            resources = rm.list_resources()
            elapsed = (time.perf_counter() - start) * 1000.0
        except Exception as exc:
            print(f"Could not list the available instruments: {exc}")
            return 1

        print(f"Found {len(resources)} instrument(s) in {elapsed:.0f} ms.")
        if len(resources) == 0:
            print("  No instruments were found.")
            print("  Make sure the signal generator is powered on and the USB cable is connected.")
            print("  On Windows, check the Zadig driver step or use NI-VISA. If using pyvisa-py,")
            print("  confirm libusb-package is installed.")
            print("  You can also run:")
            print("    python -c \"import usb.core; print(list(usb.core.find(find_all=True)))\"")
            return 1

        for index, resource in enumerate(resources):
            print(f"  [{index}] {resource}")
        address = resources[0]

    print(f"\nConnecting to: {address}")
    try:
        instr = rm.open_resource(address)
    except pyvisa.VisaIOError as exc:
        print(f"Could not connect to that instrument: {describe_visa_error(exc)}")
        return 1
    except Exception as exc:
        print(f"Something unexpected went wrong while connecting: {exc}")
        return 1

    instr.timeout = args.timeout
    instr.read_termination = "\n"
    instr.write_termination = "\n"
    print(f"Will wait up to {instr.timeout} ms for each reply.")
    print("Connected.")

    timing_log = []  # list of (command, elapsed_ms, ok)

    run_read_only_diagnostics(instr, args.trials, timing_log)

    if not args.skip_write_tests:
        run_write_tests(instr, args.channel, timing_log)
    else:
        print("\n--skip-write-tests was set: not touching the signal generator's output.")

    print_summary(timing_log)

    try:
        instr.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())