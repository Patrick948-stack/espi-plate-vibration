"""
monitor.py
Author: Patrick Mulikuza

Lets you choose the camera you want to monitor before running an ESPI
experiment, set its exposure time, gain, and gain_factor, then opens the
matching capture and display script with two live windows:

    "Live Feed"         : the raw frame straight from the camera
    "Frame Subtraction" : the difference between each pair of consecutive
                          frames, useful for checking focus and alignment
                          before starting a real sweep

Press 'q' inside either window to close the monitor and return to the
terminal.

HOW TO RUN
----------
    python3 monitor.py

DEPENDENCIES
------------
Only the SDK for the camera you actually choose needs to be installed:
    Basler        : pip install pypylon
    USB / webcam  : pip install opencv-python
    Allied Vision : pip install vmbpy (see capture_and_display_allied.py)
"""

import importlib
import math
import sys

from run_experiment import ask, ask_positive_float, section, header, clear


# ==============================================================================
# CAMERA / MODULE LOOKUP TABLES
# ==============================================================================
# Both dictionaries are keyed by the same "1" / "2" / "3" choice the user
# types in choose_camera(), so the rest of the script never has to branch on
# camera type by name, only by this one string.

_CAMERA_NAMES = {
    "1": "Basler",
    "2": "USB / webcam (eg. elp camera)",
    "3": "Allied Vision",
}

# Each capture and display module is imported lazily inside launch_monitor(),
# only after the user has picked it. That way a machine that only has one
# camera SDK installed can still run every other part of this file.
_CAPTURE_MODULES = {
    "1": "capture_and_display",
    "2": "capture_and_display_cv2",
    "3": "capture_and_display_allied",
}


# ==============================================================================
# STEP-BY-STEP QUESTIONS
# ==============================================================================
# ask_positive_float() now lives in run_experiment.py and is imported above —
# both files need the exact same "reject zero and negative numbers" rule for
# exposure and gain_factor, so it is defined once instead of drifting apart
# as two separate copies.

def choose_camera():
    """
    Displays a menu of supported cameras and asks the user to select one.

    Prints a stylized header section listing the available choices (Basler, USB/Webcam, 
    or Allied Vision) and forces the user to choose an option from the restricted list.

    Returns:
        str: The user's selection choice as a string ("1", "2", or "3").
    """
    section("Step 1 of 3 — Which camera do you want to monitor?")
    print()
    print("    1.  Basler camera")
    print("    2.  USB webcam or any other OpenCV-compatible camera such as the ELP Camera")
    print("    3.  Allied Vision camera (Vimba X)")
    print()
    return ask("Enter choice", default="2", cast=str, valid=["1", "2", "3"])


def choose_camera_index(camera_choice):
    """
    Asks the user for the physical device index of the camera.

    Different camera packages handle hardware selection differently:
    - Basler ("1"): Automatically picks the first available camera (Index 0).
    - USB ("2") / Allied Vision ("3"): Can support multiple hardware units at once, 
      so this function asks the user for a non-negative whole number (0, 1, 2...).

    Args:
        camera_choice (str): The selected camera type ("1", "2", or "3").

    Returns:
        int: The physical hardware index assigned to the camera.
    """
    if camera_choice == "1":
        return 0

    print()
    print("    Camera index 0 is the first device the SDK finds.")
    print("    If the wrong camera opens, try 1, 2, etc.")
    while True:
        index = ask("Camera index", default=0, cast=int)
        if index >= 0:
            return index
        print("  Camera index must be 0 or a positive whole number.")


def choose_camera_settings():
    """
    Prompts the user to enter experimental parameters for the camera feed.

    Guides the user through setting up three configurations:
    1. Exposure time (in seconds)
    2. Camera Gain (in decibels)
    3. Gain factor (a software contrast booster for live display only)

    Returns:
        dict: A dictionary containing the collected values map-keyed to:
              - 'exposure_s' (float)
              - 'gain_db' (float)
              - 'gain_factor' (float)
    """
    section("Step 2 of 3 — Camera settings")
    print()
    print("    Exposure is in SECONDS.  0.01 = 10 ms (good starting point).")
    print("    Increase if the image is too dark; decrease if too bright.")
    print()
    exposure_s = ask_positive_float("Exposure (s)", default=0.01)
    gain_db = ask("Gain (dB)", default=0.0, cast=float)

    print()
    print("    gain_factor multiplies the subtraction display so faint")
    print("    fringes are easier to see. It only affects what you see on")
    print("    screen, not the raw camera data.")
    gain_factor = ask_positive_float("gain_factor", default=20)

    return dict(exposure_s=exposure_s, gain_db=gain_db, gain_factor=gain_factor)


def confirm_settings(camera_choice, camera_index, settings):
    """
    Summarizes all selected configurations and asks the user for a launch confirmation.

    Prints a neat overview of the selected camera type, hardware index, exposure, 
    gain, and amplification multiplier. It then reads a confirmation string from the user.

    Args:
        camera_choice (str): The camera selection ID ("1", "2", or "3").
        camera_index (int): The physical device number of the camera.
        settings (dict): The dictionary generated by `choose_camera_settings()`.

    Returns:
        bool: True if the user confirmed with a 'yes'/'y' variant, False otherwise.
    """
    section("Step 3 of 3 — Confirm and launch")
    print()
    camera_line = _CAMERA_NAMES[camera_choice]
    if camera_choice != "1":
        camera_line += f"  (index {camera_index})"
    print(f"    Camera        :  {camera_line}")
    print(f"    Exposure      :  {settings['exposure_s']} s")
    print(f"    Gain          :  {settings['gain_db']} dB")
    print(f"    gain_factor   :  {settings['gain_factor']}")
    print()

    go = ask(
    "Open the live monitor? (y/n)",
    default="y",
    cast=lambda s: s.strip().lower(),
    valid=["y", "n", "yes", "no"],
    )
    return go in ("y", "yes")   


# ==============================================================================
# LAUNCHING THE RIGHT CAPTURE AND DISPLAY SCRIPT
# ==============================================================================

def launch_monitor(camera_choice, camera_index, settings):
    """
    Dynamically loads the proper script module and runs the real-time window loop.

    Instead of importing all camera drivers at startup, this function uses lazy importing.
    It targets only the module required for the active camera choice, allowing the system 
    to execute cleanly even if the user lacks drivers for the remaining camera models.

    It catches environment errors (like a missing pip library installation) or general runtime
    faults, printing clear, actionable instructions to the user instead of breaking with a complex
    system error traceback.

    Args:
        camera_choice (str): The camera selection ID ("1", "2", or "3").
        camera_index (int): The hardware index number of the connected camera.
        settings (dict): A configuration dictionary with 'exposure_s', 'gain_db', and 'gain_factor'.

    Returns:
        bool: True if the monitor stream finished running successfully, 
              False if an initialization error or dependency crash blocked startup.
    """
    module_name = _CAPTURE_MODULES[camera_choice]

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        print(f"\n[ERROR] Could not load {module_name}.py: {e}")
        if camera_choice == "1":
            print("  Make sure pypylon is installed: pip install pypylon")
        elif camera_choice == "2":
            print("  Make sure opencv-python is installed: pip install opencv-python")
        else:
            print("  Make sure vmbpy is installed.")
            print("  Download from: https://github.com/alliedvision/VmbPy")
            print("  Then run: pip install <downloaded_wheel>.whl")
        return False

    exposure_us = settings["exposure_s"] * 1_000_000

    try:
        if camera_choice == "1":
            module.main(
                exposure_us=exposure_us,
                gain_db=settings["gain_db"],
                gain_factor=settings["gain_factor"],
            )
        elif camera_choice == "2":
            module.main(
                camera_index=camera_index,
                exposure=math.log2(settings["exposure_s"]),
                gain=settings["gain_db"],
                gain_factor=settings["gain_factor"],
            )
        else:
            module.main(
                camera_index=camera_index,
                exposure_us=exposure_us,
                gain=settings["gain_db"],
                gain_factor=settings["gain_factor"],
            )
    except ValueError as e:
        # math.log2() raises this for exposure_s <= 0. choose_camera_settings()
        # already rejects non-positive values, so this only fires if
        # launch_monitor() is called directly with a bad settings dict.
        print(f"\n[ERROR] Invalid exposure value: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] The monitor stopped unexpectedly: {e}")
        return False

    return True


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    """
    The orchestrator and main entry point of the monitor workspace script.

    Clears the console window, renders the welcome headers, and guides the user step-by-step
    through camera selection, hardware indexing, and configuration profiling. If confirmed,
    it passes control to the underlying hardware monitoring windows.
    """
    clear()
    header()
    print("   Camera Monitor — live feed + frame subtraction preview")
    print("=" * 56)

    camera_choice = choose_camera()
    camera_index = choose_camera_index(camera_choice)
    settings = choose_camera_settings()

    if not confirm_settings(camera_choice, camera_index, settings):
        print("\n  Monitor cancelled.")
        sys.exit(0)

    print()
    launch_monitor(camera_choice, camera_index, settings)


if __name__ == "__main__":
    main()