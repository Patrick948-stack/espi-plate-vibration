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
    print(f"\n>>> Query: {command}")
    last_response = None
    for trial in range(1, trials + 1):
        elapsed, response, error = timed_call(instr.query, command)
        label = f"  trial {trial}/{trials}" if trials > 1 else "  "
        if error:
            print(f"{label} [ERROR] failed after {elapsed:.0f} ms: {error}")
            timing_log.append((command, elapsed, False))
        else:
            print(f"{label} ({elapsed:.0f} ms): {response.strip()}")
            timing_log.append((command, elapsed, True))
            last_response = response
    return last_response


def run_read_only_diagnostics(instr, trials, timing_log):
    print("\n--- Read-only diagnostics ---")
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
    print(f"\n>>> Set: {write_cmd}")
    write_elapsed, _, write_error = timed_call(instr.write, write_cmd)
    if write_error:
        print(f"  [ERROR] write failed after {write_elapsed:.0f} ms: {write_error}")
        if timing_log is not None:
            timing_log.append((write_cmd, write_elapsed, False))
        return False
    print(f"  write acknowledged in {write_elapsed:.0f} ms")
    if timing_log is not None:
        timing_log.append((write_cmd, write_elapsed, True))

    verify_cmd = f"{channel}:BSWV?"
    verify_elapsed, response, verify_error = timed_call(instr.query, verify_cmd)
    if verify_error:
        print(f"  [ERROR] verify query failed after {verify_elapsed:.0f} ms: {verify_error}")
        if timing_log is not None:
            timing_log.append((verify_cmd, verify_elapsed, False))
        return False
    if timing_log is not None:
        timing_log.append((verify_cmd, verify_elapsed, True))

    parsed = parse_bswv_response(response)
    actual = parsed.get(param_key)
    if actual is None:
        print(f"  [ERROR] verify query ({verify_elapsed:.0f} ms) did not return {param_key}")
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

    status = "OK" if ok else "MISMATCH"
    print(f"  verify ({verify_elapsed:.0f} ms): {param_key} = {actual}  [{status}, expected {expect_value}]")
    return ok


def run_write_tests(instr, channel, timing_log):
    print(f"\n--- Write-and-verify tests on channel {channel} ---")

    save_cmd = f"{channel}:BSWV?"
    elapsed, original_response, error = timed_call(instr.query, save_cmd)
    if error:
        print(f"[ERROR] Could not read original waveform state, skipping write tests: {error}")
        return
    timing_log.append((save_cmd, elapsed, True))
    original_response = original_response.strip()
    print(f"Saved original state ({elapsed:.0f} ms): {original_response}")

    results = []
    results.append(set_and_verify(
        instr, channel, "WVTP", "SQUARE", "SQUARE", timing_log=timing_log))
    results.append(set_and_verify(
        instr, channel, "FRQ", "2000HZ", "2000HZ", numeric=True, timing_log=timing_log))
    results.append(set_and_verify(
        instr, channel, "AMP", "1V", "1V", numeric=True, timing_log=timing_log))

    print(f"\nRestoring original state: {original_response}")
    elapsed, _, error = timed_call(instr.write, original_response)
    if error:
        print(f"[ERROR] Restore failed after {elapsed:.0f} ms: {error}")
        print("  Instrument may be left in the test state above. Restore manually if needed.")
    else:
        print(f"  restored in {elapsed:.0f} ms")
    timing_log.append((f"{channel}:BSWV (restore)", elapsed, error is None))

    passed = sum(1 for r in results if r)
    print(f"\nWrite tests: {passed}/{len(results)} passed.")


# ---------------------------------------------------------------------
# Setup / main
# ---------------------------------------------------------------------

def connect(backend):
    if backend:
        print(f"Starting VISA ResourceManager with backend: {backend}")
        return pyvisa.ResourceManager(backend)
    print("Starting VISA ResourceManager with default backend.")
    return pyvisa.ResourceManager()


def print_summary(timing_log):
    print("\n=== Summary ===")
    slow = [(cmd, ms) for cmd, ms, ok in timing_log if ok and ms > SLOW_THRESHOLD_MS]
    failed = [cmd for cmd, ms, ok in timing_log if not ok]

    if not slow and not failed:
        print(f"All {len(timing_log)} commands completed under {SLOW_THRESHOLD_MS:.0f} ms.")
        return

    if slow:
        print(f"Commands slower than {SLOW_THRESHOLD_MS:.0f} ms:")
        for cmd, ms in slow:
            print(f"  {ms:7.0f} ms  {cmd}")
    if failed:
        print("Commands that failed:")
        for cmd in failed:
            print(f"  FAILED  {cmd}")


def main():
    parser = argparse.ArgumentParser(
        description="Debug slow signal generator response time, and test set/verify commands via PyVISA."
    )
    parser.add_argument("--backend", default=None,
                         help="Optional PyVISA backend string, e.g. '@py' or '@ni'.")
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

    print("Signal generator response debugger")
    print("===================================\n")

    try:
        rm = connect(args.backend)
    except Exception as exc:
        print(f"[ERROR] Could not start VISA ResourceManager: {exc}")
        print("  Make sure pyvisa and a backend driver are installed.")
        print("  Example: pip install pyvisa pyvisa-py libusb-package")
        return 1

    try:
        backend_path = rm.visalib.library_path
    except Exception:
        backend_path = "unknown"
    print(f"VISA backend path: {backend_path}")

    if args.address:
        address = args.address
    else:
        try:
            start = time.perf_counter()
            resources = rm.list_resources()
            elapsed = (time.perf_counter() - start) * 1000.0
        except Exception as exc:
            print(f"[ERROR] Could not list VISA resources: {exc}")
            return 1

        print(f"Found {len(resources)} VISA resource(s) in {elapsed:.0f} ms.")
        if len(resources) == 0:
            print("  No instruments were discovered.")
            print("  Make sure the signal generator is powered on and the USB cable is connected.")
            print("  On Windows, check Zadig or use NI-VISA. If using pyvisa-py, confirm libusb-package is installed.")
            print("  You can also run:")
            print("    python -c \"import usb.core; print(list(usb.core.find(find_all=True)))\"")
            return 1

        for index, resource in enumerate(resources):
            print(f"  [{index}] {resource}")
        address = resources[0]

    print(f"\nOpening resource: {address}")
    try:
        instr = rm.open_resource(address)
    except pyvisa.VisaIOError as exc:
        print(f"[ERROR] Could not open resource: {describe_visa_error(exc)}")
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected failure opening resource: {exc}")
        return 1

    instr.timeout = args.timeout
    instr.read_termination = "\n"
    instr.write_termination = "\n"
    print(f"Instrument timeout set to {instr.timeout} ms.")
    print("Instrument opened successfully.")

    timing_log = []  # list of (command, elapsed_ms, ok)

    run_read_only_diagnostics(instr, args.trials, timing_log)

    if not args.skip_write_tests:
        run_write_tests(instr, args.channel, timing_log)
    else:
        print("\n--skip-write-tests set: not touching waveform output.")

    print_summary(timing_log)

    try:
        instr.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())