"""
limits.py
Hardware safety limits for the Siglent SDG1015.

Clamp functions only — nothing here talks to the instrument, which means
this module can be unit-tested without any hardware connected.
"""

# Hardware frequency limits per waveform type: (min Hz, max Hz)
FREQUENCY_LIMITS = {
    "sine":   (1e-6, 15e6),
    "square": (1e-6, 15e6),
    "ramp":   (1e-6,  3e5),
    "pulse":  (5e-4,  5e6),
    "arb":    (1e-6,  5e6),
    "noise":  (1e-6, 50e6),
}

MIN_AMPLITUDE = 0.002   # 2 mVpp
MAX_AMPLITUDE = 20.0    # 20 Vpp
VOLTAGE_RAIL = 10.0     # ±10 V internal rail


def clamp_frequency(frequency, waveform="sine"):
    """Clamp a frequency (Hz) into the legal range for the given waveform."""
    min_f, max_f = FREQUENCY_LIMITS.get(waveform.lower(), (1e-6, 15e6))
    clamped = max(min_f, min(frequency, max_f))
    if clamped != frequency:
        print(f"[WARNING] Frequency {frequency} Hz is out of range for "
              f"'{waveform}'. Clamped to {clamped} Hz.")
    return clamped


def clamp_amplitude(amplitude):
    """Clamp an amplitude (Vpp) into the instrument's 2 mVpp – 20 Vpp range."""
    clamped = max(MIN_AMPLITUDE, min(amplitude, MAX_AMPLITUDE))
    if clamped != amplitude:
        print(f"[WARNING] Amplitude {amplitude} Vpp is out of range. "
              f"Clamped to {clamped} Vpp.")
    return clamped


def clamp_offset(offset, amplitude=0.0):
    """
    Clamp a DC offset (V) so that offset ± amplitude/2 never exceeds
    the ±10 V output rail.
    """
    max_offset = max(0.0, VOLTAGE_RAIL - abs(amplitude / 2.0))
    clamped = max(-max_offset, min(offset, max_offset))
    if clamped != offset:
        print(f"[WARNING] Offset {offset} V is out of safe range. "
              f"Clamped to {clamped} V.")
    return clamped