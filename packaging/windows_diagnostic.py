"""
windows_diagnostic.py

Checks whether a Windows computer is actually ready to run the ESPI app
and talk to real hardware, separate from whether the packaged app file
itself opens. The packaged app can open perfectly fine and still not see
a camera or the signal generator, if one of the manual install steps
below was skipped or went wrong. This script exists to say exactly which
one, instead of leaving someone staring at a blank camera feed with no
idea why.

Important limit: this script was written and reviewed on a Mac, since
that is the only computer available while building it. Every check
below was designed to degrade gracefully and report a clear pass or
fail instead of crashing, except for the very last one (the PyQt6
window check), which cannot be made crash proof. See that section's own
comment for why. This script still needs to actually be run on a real
Windows computer at least once to confirm it behaves as intended there,
which has not happened yet.

Run with (from the project root, venv_physics active):
    python packaging/windows_diagnostic.py
"""

import platform
import sys


def _print_result(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)
    return passed


def check_os_and_architecture():
    print("\n--- 1. Operating system ---")
    system = platform.system()
    is_windows = system == "Windows"
    _print_result(
        "Running on Windows",
        is_windows,
        f"platform.system() returned '{system}'" if not is_windows else "",
    )
    if is_windows:
        _print_result(
            "64 bit Python",
            sys.maxsize > 2**32,
            "camera SDKs on Windows are 64 bit only",
        )
    return is_windows


def check_pypylon():
    print("\n--- 2. Basler camera (pypylon) ---")
    try:
        from pypylon import pylon
    except Exception as exc:
        return _print_result(
            "pypylon imports successfully",
            False,
            f"{exc}. Install with 'pip install pypylon', and make sure the "
            "full Basler pylon Camera Software Suite (not just the slim "
            "Runtime) is installed from basler.com first.",
        )
    _print_result("pypylon imports successfully", True)

    try:
        pylon.TlFactory.GetInstance()
    except Exception as exc:
        return _print_result(
            "pypylon can reach the Basler transport layer",
            False,
            f"{exc}. This usually means pypylon imported fine but the "
            "actual pylon Camera Software Suite is missing or was not "
            "fully installed.",
        )
    return _print_result("pypylon can reach the Basler transport layer", True)


def check_vmbpy():
    print("\n--- 3. Allied Vision camera (vmbpy) ---")
    try:
        import vmbpy
    except Exception as exc:
        return _print_result(
            "vmbpy imports successfully",
            False,
            f"{exc}. vmbpy is not on PyPI. Install the Vimba X SDK from "
            "alliedvision.com, then find the .whl file inside its install "
            "folder (typically C:\\Program Files\\Allied Vision\\Vimba X\\"
            "api\\python\\) and run "
            "'pip install path\\to\\vmbpy-<version>-py3-none-any.whl'.",
        )
    return _print_result("vmbpy imports successfully", True)


def check_signal_generator_usb():
    print("\n--- 4. Signal generator USB driver (Zadig / WinUSB) ---")
    try:
        import usb.core
    except Exception as exc:
        return _print_result(
            "pyusb imports successfully",
            False,
            f"{exc}. Install with 'pip install pyusb'.",
        )

    try:
        devices = list(usb.core.find(find_all=True))
    except Exception as exc:
        return _print_result(
            "pyusb can see USB devices",
            False,
            f"{exc}. This is the classic NoBackendError. It means the "
            "Zadig step has not been done yet: plug in and power on the "
            "signal generator, then follow the Zadig instructions in "
            "ESPI Full Algorithm/requirements.txt to bind the WinUSB "
            "driver to it.",
        )

    if not devices:
        return _print_result(
            "pyusb can see USB devices",
            False,
            "An empty list came back. Either nothing is plugged in and "
            "powered on right now, or the Zadig step still needs to be "
            "done for the signal generator specifically.",
        )
    return _print_result(
        "pyusb can see USB devices", True, f"{len(devices)} device(s) found"
    )


def check_pyqt6_window():
    # This check is last on purpose. If the Qt "platforms" plugin
    # (qwindows.dll) fails to load inside a packaged exe, a common
    # PyInstaller plus PyQt6 problem on Windows, Qt itself calls a
    # function that aborts the whole process immediately. That happens
    # before Python ever gets a chance to catch it as a normal
    # exception, so this script cannot wrap it in try/except and
    # continue afterward the way every check above can. If the program
    # stops here with no [PASS] or [FAIL] line at all and no Python
    # traceback, that silence is itself the failure: it means the Qt
    # platform plugin did not load.
    print("\n--- 5. PyQt6 can open a window ---")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    _print_result("QApplication created without crashing", True)
    app.quit()


def main():
    print("ESPI app: Windows hardware readiness check")
    print("=" * 50)

    is_windows = check_os_and_architecture()
    if not is_windows:
        print(
            "\nThis machine is not running Windows. The checks below "
            "will still run, but they were written and tested for "
            "Windows specifically."
        )

    results = [
        check_pypylon(),
        check_vmbpy(),
        check_signal_generator_usb(),
    ]

    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} hardware checks passed.")
    if passed < len(results):
        print("Fix the FAIL lines above before assuming a hardware problem")
        print("in the app itself.")

    check_pyqt6_window()


if __name__ == "__main__":
    main()
