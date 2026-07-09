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
    print("=== STARTING BASLER PYLON DEBUG DIAGNOSTIC ===")
    
    # -------------------------------------------------------------
    # STEP 1: Check Windows Environment & Pylon Installation Path
    # -------------------------------------------------------------
    print("\n[1/5] Checking Windows Environment Variables...")
    pylon_dev_dir = find_pylon_sdk_dir()
    
    if pylon_dev_dir:
        print(f" -> SUCCESS: Pylon SDK installation found at: {pylon_dev_dir}")
        # Dynamically map the path so Python knows exactly where to look for C++ drivers
        os.environ['PYLON_DEV_DIR'] = pylon_dev_dir
    else:
        print(" -> ERROR: No Basler Pylon SDK directory was found.")
        print("    REASON: The native Basler Pylon Runtime/SDK for Windows is not installed or not in a standard location.")
        print("    FIX: Download and install 'pylon Camera Software Suite for Windows' from Basler.")
        return

    # -------------------------------------------------------------
    # STEP 2: Check for Windows OS Subsystem Blocks (WSL/WSL2)
    # -------------------------------------------------------------
    print("\n[2/5] Checking Environment Layer...")
    # Industrial USB3 vision cameras cannot pass through native WSL2 USB architecture easily.
    if platform.system() == 'Linux' and 'microsoft' in platform.release().lower():
        print(" -> ERROR: You are running Python inside WSL/WSL2 (Linux subsystem).")
        print("    REASON: WSL does not natively support USB3 Vision transport layers.")
        print("    FIX: Execute your script using native Windows Command Prompt or PowerShell.")
        return
    else:
        print(" -> SUCCESS: Running on native host system.")

    # -------------------------------------------------------------
    # STEP 3: Verify the Windows Device Manager Class Driver
    # -------------------------------------------------------------
    print("\n[3/5] Querying Windows Device Manager for Basler/USB Vision Hardware...")
    try:
        raw_output = query_windows_pnp_devices()

        # If the string is empty or returned our custom failure message
        if not raw_output or raw_output.startswith('<device-query-failed'):
            print(" -> ERROR: Could not query relevant Windows device entries automatically.")
            print("    MANUAL FIX: Verify the camera shows up under 'Cameras' or 'Imaging devices' in Device Manager.")
            return

        print(" -> Windows device entries found:")
        print(f"\n{raw_output}\n")

        # Check if the text output contains any variations of the keyword 'vision'
        if any(token in raw_output.lower() for token in ['usb vision', 'usb3 vision', 'vision device']):
            print(" -> INFO: Windows sees the camera as a USB Vision device.")
            print("    This is a stronger signal than 'no device' and suggests the camera is present,")
            print("    but the pylon driver/transport layer is not yet being enumerated correctly.")
        elif 'camera' not in raw_output.lower():
            print(" -> WARN: The camera does not appear under the expected camera-related classes.")
            print("    FIX: Open the Basler pylon USB Configurator or check whether the device is being exposed under 'Universal Serial Bus devices' or 'Imaging devices'.")
            return

    except Exception as e:
        # A safety net in case checking the string contents raises an unexpected code bug
        print(f" -> Code could not query Device Manager automatically: {e}")
        print("    MANUAL FIX: Manually verify the camera shows up under 'Imaging devices' or 'Cameras' inside Windows Device Manager.")

    # -------------------------------------------------------------
    # STEP 4: Initialize Transport Layer and Enumerate Devices
    # -------------------------------------------------------------
    print("\n[4/5] Initializing pypylon Transport Layer Factory...")
    try:
        # Access Basler's core software factory responsible for managing device drivers
        tl_factory = pylon.TlFactory.GetInstance()
        # Look for physical cameras plugged into ports
        devices = tl_factory.EnumerateDevices()
        
        print(f" -> Transport layer initialized. Total Basler cameras discovered: {len(devices)}")
        
        if len(devices) == 0:
            print(" -> ERROR: Pylon library is healthy, but 'EnumerateDevices()' returned 0 hardware units.")
            print("    REASON: Windows can see the device, but the Basler pylon transport layer still is not enumerating it.")
            print("            This often points to a driver-binding problem, a stale pylon runtime state, or another")
            print("            application (such as pylon Viewer) holding the device open.")
            print("    FIX: Close other software instances, restart the pylon runtime, and try the Basler 'pylon USB Configurator'.")
            return
            
        # Loop through each found camera and print its unique identity specs
        for i, device_info in enumerate(devices):
            print(f"    [Camera {i}]: Model: {device_info.GetModelName()} | SN: {device_info.GetSerialNumber()} | Connection: {device_info.GetDeviceClass()}")
            
    except Exception as e:
        # If pypylon crashes immediately when calling GetInstance(), Python can't connect to the drivers at all
        print(f" -> CRITICAL ERROR: pypylon bindings crashed during factory enumeration: {e}")
        print("    FIX: Reinstall the python wheel using: pip install --force-reinstall pypylon")
        return

    # -------------------------------------------------------------
    # STEP 5: Attempt Hardware Initialization and Open Command
    # -------------------------------------------------------------
    print("\n[5/5] Attempting to hook and open the primary camera device...")
    try:
        # Bind the very first camera discovered index [0] to an InstantCamera object
        camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
        
        # Test physical communication line open (this boots up the camera handshake)
        camera.Open()
        print(f" -> SUCCESS: Camera '{camera.GetDeviceInfo().GetModelName()}' successfully locked and opened!")
        
        # Safely shut down connection so other programs can use it afterwards
        camera.Close()
        print(" -> Connection closed cleanly. Your python pypylon stack is working perfectly.")
        
    except pylon.RuntimeException as runtime_err:
        # Handle errors specific to Basler's internal system (e.g., bandwidth or busy issues)
        print(f" -> ERROR: Found the camera but failed to initialize it: {runtime_err}")
        print("    REASON: Typically means the camera is already locked by another process (like pylon Viewer)")
        print("            or the USB host controller cannot handle the packet size/bandwidth demands.")
    except Exception as general_err:
        # Handle any other generic errors (e.g., script issues, cable sudden disconnections)
        print(f" -> UNEXPECTED ERROR: {general_err}")


# This prevents code from automatically running if imported into another script as a module
if __name__ == "__main__":
    debug_basler_pylon_connection()