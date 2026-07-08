import sys

try:
    import pyvisa
except Exception as exc:
    print(f"pyvisa import failed: {exc}")
    sys.exit(1)

try:
    import usb.core
except Exception as exc:
    print(f"pyusb import failed: {exc}")
    sys.exit(1)

print("Scanning for USB devices...")
try:
    devices = list(usb.core.find(find_all=True))
    if devices:
        print(f"Found {len(devices)} USB device(s):")
        for dev in devices:
            print(f"- {dev.manufacturer} {dev.product} (idVendor={dev.idVendor:#06x}, idProduct={dev.idProduct:#06x})")
    else:
        print("No USB devices found via pyusb.")
except Exception as exc:
    print(f"USB scan failed: {exc}")

print("\nScanning for VISA instruments...")
try:
    rm = pyvisa.ResourceManager('@py')
    resources = rm.list_resources()
    if resources:
        print("Found VISA resources:")
        for resource in resources:
            print(f"- {resource}")
    else:
        print("No VISA resources found.")
except Exception as exc:
    print(f"VISA scan failed: {exc}")
