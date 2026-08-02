"""
sdg_control — control library for the Siglent SDG1015 signal generator.

Typical usage:
    from sdg_control import open_connection, configure_channel, close_connection
"""

from .connections import (
    get_resource_manager,
    discover_instruments,
    find_instruments,
    connect_instrument,
    open_connection,
    close_connection,
)
from .status import get_identity, get_output_status, get_wave_status
from .output import turn_on_output, turn_off_output
from .waveform import (
    set_waveform,
    set_frequency,
    set_amplitude,
    set_offset,
    configure_channel,
)
from .limits import clamp_frequency, clamp_amplitude, clamp_offset
from .constants import COMMAND_SETTLE_S, OUTPUT_SETTLE_S

__all__ = [
    "get_resource_manager", "discover_instruments", "find_instruments", "connect_instrument", "open_connection",
    "close_connection", "get_identity", "get_output_status",
    "get_wave_status", "turn_on_output", "turn_off_output",
    "set_waveform", "set_frequency", "set_amplitude", "set_offset",
    "configure_channel", "clamp_frequency", "clamp_amplitude",
    "clamp_offset", "COMMAND_SETTLE_S", "OUTPUT_SETTLE_S",
]