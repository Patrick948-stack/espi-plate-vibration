import sys

try:
    import pyvisa
except Exception as exc:
    print(f"Could not load the pyvisa package: {exc}")
    print("Make sure you ran 'pip install -r requirements.txt' with the virtual environment active.")
    sys.exit(1)

try:
    import usb.core
except Exception as exc:
    print(f"Could not load the pyusb package: {exc}")
    print("Make sure you ran 'pip install -r requirements.txt' with the virtual environment active.")
    sys.exit(1)

print("Step 1: checking what USB devices your computer can see, without pyvisa involved...")
try:
    devices = list(usb.core.find(find_all=True))
    if devices:
        print(f"Found {len(devices)} USB device(s) plugged in:")
        for dev in devices:
            print(f"- {dev.manufacturer} {dev.product} (idVendor={dev.idVendor:#06x}, idProduct={dev.idProduct:#06x})")
    else:
        print("No USB devices found at all.")
        print("This usually means a driver-level problem, not a Python problem: check the USB")
        print("cable and that the instrument is powered on. On Windows, see the Zadig driver")
        print("step in the README's signal generator setup section.")
except Exception as exc:
    print(f"Could not scan for USB devices: {exc}")

print("\nStep 2: checking which of those devices pyvisa recognizes as instruments...")
try:
    rm = pyvisa.ResourceManager('@py')
    resources = rm.list_resources()
    if resources:
        print("pyvisa found these instrument(s):")
        for resource in resources:
            print(f"- {resource}")
    else:
        print("pyvisa did not find any instruments.")
        print("If Step 1 found USB devices but this step found nothing, the instrument is")
        print("plugged in but not yet recognized as something pyvisa can talk to; see the")
        print("README's signal generator setup section.")
except Exception as exc:
    print(f"Could not scan for VISA instruments: {exc}")
