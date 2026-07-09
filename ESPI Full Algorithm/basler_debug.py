"""
Basler Pylon Camera Diagnostic Tool
Author: patrick mulikuza

This script diagnoses connection and environment issues between Python and
Basler industrial cameras using the `pypylon` library. It walks through a
5-step verification checklist to ensure drivers, hardware, and libraries
are communicating correctly.
"""

import os
import platform
import subprocess
from pypylon import pylon


def find_pylon_sdk_dir():
    """
    Locate the Basler pylon SDK directory on a Windows operating system.

    Checks environment variables first, then falls back to checking standard
    64-bit and 32-bit Program Files installation paths.

    Returns:
        str: The absolute path to the SDK directory if found.
        None: If the directory could not be located.
    """
    candidates = []

    # Check if Windows already has the pylon path stored in system environment variables
    env_dir = os.environ.get('PYLON_DEV_DIR') or os.environ.get('PYLON_ROOT') or os.environ.get('PYLONC_ROOT')
    if env_dir:
        candidates.append(env_dir)

    # Standard default installation paths for Basler software on Windows
    candidates.extend([
        r'C:\Program Files\Basler\pylon',
        r'C:\Program Files\Basler\pylon 5',
        r'C:\Program Files (x86)\Basler\pylon',
    ])

    # Loop through paths and return the first one that actually exists on the hard drive
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate

    return None


def query_windows_pnp_devices():
    """
    Query Windows Device Manager via PowerShell for connected hardware.

    Filters for devices with names/descriptions matching 'Basler', 'pylon',
    or 'Vision' to see if the operating system detects the hardware at all.

    Returns:
        str: A formatted table listing discovered devices, or an error message string.
    """
    # Define a PowerShell command to filter Plug-and-Play (Pnp) devices.
    # The backslashes allow us to format a long string cleanly across multiple lines.
    ps_cmd = (
        "powershell -NoProfile -Command \""
        "Get-PnpDevice -ErrorAction SilentlyContinue | "
        "Where-Object { ($_.FriendlyName -match 'Basler|pylon|USB Vision|USB3 Vision|Vision') -or "
        "($_.Description -match 'Basler|USB Vision|USB3 Vision|Vision') } | "
        "Select-Object FriendlyName, Description, Status, Class | "
        "Format-Table -AutoSize"
        "\""
    )

    try:
        # Run the command silently in the background and capture what it prints out
        return subprocess.check_output(ps_cmd, shell=True, text=True).strip()
    except Exception as exc:
        # If PowerShell fails or is restricted, catch the error and return a safe message
        return f"<device-query-failed: {exc}>"


def debug_basler_pylon_connection():
    """
    Execute a sequential 5-step diagnostic pipeline to find and test
    attached Basler camera hardware and its software configurations.
    """
    print("Basler camera diagnostic tool")
    print("This checks, one step at a time, why Python might not be able to see your Basler camera.")

    # -------------------------------------------------------------
    # STEP 1: Check Windows Environment & Pylon Installation Path
    # -------------------------------------------------------------
    print("\n[1/5] Looking for the Basler pylon software on this computer...")
    pylon_dev_dir = find_pylon_sdk_dir()

    if pylon_dev_dir:
        print(f" -> Found it. The Basler pylon software is installed at: {pylon_dev_dir}")
        # Dynamically map the path so Python knows exactly where to look for C++ drivers
        os.environ['PYLON_DEV_DIR'] = pylon_dev_dir
    else:
        print(" -> Could not find the Basler pylon software on this computer.")
        print("    Likely cause: the pylon Camera Software Suite is not installed, or it is")
        print("    installed somewhere this script does not know to look.")
        print("    What to do: download and install the full pylon Camera Software Suite from")
        print("    Basler's website (see this project's README, Stage 8, for exact steps),")
        print("    then run this script again.")
        return

    # -------------------------------------------------------------
    # STEP 2: Check for Windows OS Subsystem Blocks (WSL/WSL2)
    # -------------------------------------------------------------
    print("\n[2/5] Checking whether Python is running directly on Windows...")
    # Industrial USB3 vision cameras cannot pass through native WSL2 USB architecture easily.
    if platform.system() == 'Linux' and 'microsoft' in platform.release().lower():
        print(" -> This script is running inside WSL (Windows Subsystem for Linux), not Windows itself.")
        print("    That is a problem: USB cameras like this one cannot be reached from inside WSL.")
        print("    What to do: close this and run the script again from a normal Windows")
        print("    Command Prompt or PowerShell window, not from a WSL or Linux terminal.")
        return
    else:
        print(" -> Good, this is running directly on Windows.")

    # -------------------------------------------------------------
    # STEP 3: Verify the Windows Device Manager Class Driver
    # -------------------------------------------------------------
    print("\n[3/5] Checking Windows Device Manager to see if it notices the camera...")
    try:
        raw_output = query_windows_pnp_devices()

        # If the string is empty or returned our custom failure message
        if not raw_output or raw_output.startswith('<device-query-failed'):
            print(" -> Could not check Device Manager automatically.")
            print("    What to do: open Device Manager yourself and look for the camera under")
            print("    'Cameras' or 'Imaging devices'.")
            return

        print(" -> Windows found these matching devices:")
        print(f"\n{raw_output}\n")

        # Check if the text output contains any variations of the keyword 'vision'
        if any(token in raw_output.lower() for token in ['usb vision', 'usb3 vision', 'vision device']):
            print(" -> Windows can see the camera; it shows up as a USB Vision device.")
            print("    That is a good sign, the camera itself is connected. If the next steps")
            print("    still fail, the problem is the pylon driver talking to it, not the USB")
            print("    connection itself.")
        elif 'camera' not in raw_output.lower():
            print(" -> Windows does not seem to recognize this as a camera yet.")
            print("    What to do: open the Basler pylon USB Configurator (installed with the")
            print("    pylon software), or check Device Manager under 'Universal Serial Bus")
            print("    devices' or 'Imaging devices' to see how Windows currently sees it.")
            return

    except Exception as e:
        # A safety net in case checking the string contents raises an unexpected code bug
        print(f" -> Could not check Device Manager automatically: {e}")
        print("    What to do: open Device Manager yourself and check under 'Imaging devices'")
        print("    or 'Cameras'.")

    # -------------------------------------------------------------
    # STEP 4: Initialize Transport Layer and Enumerate Devices
    # -------------------------------------------------------------
    print("\n[4/5] Asking the pylon software to list every camera it can find...")
    try:
        # Access Basler's core software factory responsible for managing device drivers
        tl_factory = pylon.TlFactory.GetInstance()
        # Look for physical cameras plugged into ports
        devices = tl_factory.EnumerateDevices()

        print(f" -> The pylon software started up correctly. Cameras it can see: {len(devices)}")

        if len(devices) == 0:
            print(" -> The pylon software is working, but it cannot find any cameras.")
            print("    Likely cause: Windows sees the device (Step 3 above), but the pylon")
            print("    driver is not recognizing it as a camera yet. This often happens if")
            print("    another program (such as pylon Viewer) already has the camera open,")
            print("    or if the driver just needs to be reset.")
            print("    What to do: close any other program that might be using the camera")
            print("    (including pylon Viewer), then try the Basler pylon USB Configurator,")
            print("    or unplug and replug the camera.")
            return

        # Loop through each found camera and print its unique identity specs
        for i, device_info in enumerate(devices):
            print(f"    [Camera {i}]: Model: {device_info.GetModelName()} | SN: {device_info.GetSerialNumber()} | Connection: {device_info.GetDeviceClass()}")

    except Exception as e:
        # If pypylon crashes immediately when calling GetInstance(), Python can't connect to the drivers at all
        print(f" -> Something went wrong while pypylon (the Python package for Basler cameras)")
        print(f"    tried to start up: {e}")
        print("    What to do: try reinstalling it with: pip install --force-reinstall pypylon")
        return

    # -------------------------------------------------------------
    # STEP 5: Attempt Hardware Initialization and Open Command
    # -------------------------------------------------------------
    print("\n[5/5] Trying to actually open a connection to the camera...")
    try:
        # Bind the very first camera discovered index [0] to an InstantCamera object
        camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())

        # Test physical communication line open (this boots up the camera handshake)
        camera.Open()
        print(f" -> Success. Connected to the camera: {camera.GetDeviceInfo().GetModelName()}")

        # Safely shut down connection so other programs can use it afterwards
        camera.Close()
        print(" -> Closed the connection cleanly. Everything is working correctly: Python")
        print("    can find and talk to this camera.")

    except pylon.RuntimeException as runtime_err:
        # Handle errors specific to Basler's internal system (e.g., bandwidth or busy issues)
        print(f" -> Found the camera, but could not open a connection to it: {runtime_err}")
        print("    Likely cause: another program (such as pylon Viewer) already has the")
        print("    camera open, or your computer's USB port cannot keep up with the amount")
        print("    of data the camera is trying to send.")
        print("    What to do: close any other program using the camera, and if possible")
        print("    try a different USB port (ideally USB 3.0, plugged in directly rather")
        print("    than through a hub).")
    except Exception as general_err:
        # Handle any other generic errors (e.g., script issues, cable sudden disconnections)
        print(f" -> Something unexpected went wrong: {general_err}")


# This prevents code from automatically running if imported into another script as a module
if __name__ == "__main__":
    debug_basler_pylon_connection()
