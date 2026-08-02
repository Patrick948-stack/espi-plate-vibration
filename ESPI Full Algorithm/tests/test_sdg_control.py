"""
test_sdg_control.py
Tests for the sdg_control package (Siglent SDG1015 via pyvisa).

Ported from tests/test_signal_generator_control.py, since sdg_control's
connections.py/status.py/output.py/waveform.py were built to have the same
externally-visible behavior as signal_generator_control.py's equivalent
functions (error diagnostics included), just split into focused modules
instead of one file. sdg_control is imported through its package __init__,
so `sg.find_instruments(...)`, `sg.turn_on_output(...)`, etc. all work the
same way `sg.` did against the old monolithic module -- only the internal
`patch(...)` targets differ, since they now point at whichever specific
submodule actually defines the name being patched.

Sections covered
----------------
  clamp_frequency, clamp_amplitude, clamp_offset (limits.py)

  Hardware functions (pyvisa.ResourceManager mocked):
    find_instruments, connect_instrument, open_connection, close_connection
    (connections.py), get_identity, get_output_status, get_wave_status
    (status.py), turn_on_output, turn_off_output (output.py), set_waveform,
    set_frequency, set_amplitude, set_offset, configure_channel (waveform.py)

  Error diagnostics (errors.py): describe_visa_error, require_instrument,
  and every function's None-instrument guard.

Deliberate differences from signal_generator_control.py, reflected below:
  - sdg_control.waveform.configure_channel() does NOT turn the output on
    and does NOT return a "channel output" key -- unlike the old module's
    configure_channel(), which does both. Configuring a channel and
    enabling its output are two separate, single-responsibility calls
    here (see turn_on_output() in output.py). Callers that need the
    output on must call turn_on_output() themselves afterward -- this is
    exactly what complete_pipeline.py, complete_pipeline_inclusive.py, and
    complete_pipeline_allied_vision.py now do.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sdg_control as sg
import sdg_control.connections as sg_connections
import sdg_control.errors as sg_errors

from conftest import make_mock_instrument


# ===========================================================================
# SECTION 1 — CLAMP FUNCTIONS (pure logic)
# ===========================================================================

class TestClampFrequency:
    # --- Within-range values should pass through unchanged ---
    def test_sine_within_range_unchanged(self):
        assert sg.clamp_frequency(1000.0, "sine") == 1000.0

    def test_ramp_within_range_unchanged(self):
        assert sg.clamp_frequency(100_000.0, "ramp") == 100_000.0

    def test_pulse_within_range_unchanged(self):
        assert sg.clamp_frequency(1_000.0, "pulse") == 1_000.0

    # --- Too-high values are clamped to the waveform maximum ---
    def test_sine_above_max_clamped_to_15mhz(self):
        result = sg.clamp_frequency(20e6, "sine")
        assert result == 15e6

    def test_ramp_above_max_clamped_to_300khz(self):
        result = sg.clamp_frequency(5e6, "ramp")
        assert result == 3e5

    def test_square_above_max_clamped(self):
        result = sg.clamp_frequency(20e6, "square")
        assert result == 15e6

    def test_pulse_above_max_clamped_to_5mhz(self):
        result = sg.clamp_frequency(10e6, "pulse")
        assert result == 5e6

    def test_arb_above_max_clamped_to_5mhz(self):
        result = sg.clamp_frequency(10e6, "arb")
        assert result == 5e6

    def test_noise_above_max_clamped_to_50mhz(self):
        result = sg.clamp_frequency(100e6, "noise")
        assert result == 50e6

    # --- Too-low values are clamped to 1 uHz minimum ---
    def test_below_min_clamped_to_1uhz(self):
        result = sg.clamp_frequency(0.0, "sine")
        assert result == 1e-6

    def test_negative_frequency_clamped(self):
        result = sg.clamp_frequency(-500.0, "sine")
        assert result == 1e-6

    # --- Exact boundaries should pass unchanged ---
    def test_sine_at_exact_max_unchanged(self):
        assert sg.clamp_frequency(15e6, "sine") == 15e6

    def test_sine_at_exact_min_unchanged(self):
        assert sg.clamp_frequency(1e-6, "sine") == 1e-6

    # --- Case-insensitive waveform names ---
    def test_case_insensitive_waveform_name(self):
        result = sg.clamp_frequency(20e6, "SINE")
        assert result == 15e6

    def test_mixed_case_waveform_name(self):
        result = sg.clamp_frequency(20e6, "Ramp")
        assert result == 3e5

    # --- Unknown waveform falls back to sine limits ---
    def test_unknown_waveform_uses_sine_limits(self):
        result = sg.clamp_frequency(20e6, "unknown_waveform")
        assert result == 15e6


class TestClampAmplitude:
    def test_within_range_unchanged(self):
        assert sg.clamp_amplitude(5.0) == 5.0

    def test_above_max_clamped_to_20vpp(self):
        assert sg.clamp_amplitude(25.0) == 20.0

    def test_below_min_clamped_to_2mvpp(self):
        assert sg.clamp_amplitude(0.0) == 0.002

    def test_negative_clamped_to_min(self):
        assert sg.clamp_amplitude(-1.0) == 0.002

    def test_at_exact_max_unchanged(self):
        assert sg.clamp_amplitude(20.0) == 20.0

    def test_at_exact_min_unchanged(self):
        assert sg.clamp_amplitude(0.002) == 0.002

    def test_large_amplitude_clamped(self):
        assert sg.clamp_amplitude(1000.0) == 20.0


class TestClampOffset:
    def test_zero_offset_zero_amplitude_unchanged(self):
        assert sg.clamp_offset(0.0, 0.0) == 0.0

    def test_positive_offset_within_range(self):
        # amplitude=4 Vpp -> peaks swing +-2 V -> max offset = 10 - 2 = 8 V
        assert sg.clamp_offset(5.0, amplitude=4.0) == 5.0

    def test_negative_offset_within_range(self):
        assert sg.clamp_offset(-5.0, amplitude=4.0) == -5.0

    def test_offset_clamped_when_above_limit(self):
        # amplitude=4 Vpp, max offset = 8 V; request 9 V -> clamped to 8 V
        result = sg.clamp_offset(9.0, amplitude=4.0)
        assert result == pytest.approx(8.0)

    def test_offset_clamped_when_below_negative_limit(self):
        result = sg.clamp_offset(-9.0, amplitude=4.0)
        assert result == pytest.approx(-8.0)

    def test_max_amplitude_forces_zero_offset(self):
        # 20 Vpp -> peaks swing +-10 V -> offset must be 0
        result = sg.clamp_offset(1.0, amplitude=20.0)
        assert result == 0.0

    def test_zero_amplitude_allows_full_10v_range(self):
        assert sg.clamp_offset(9.9, amplitude=0.0) == 9.9
        assert sg.clamp_offset(-9.9, amplitude=0.0) == -9.9

    def test_default_amplitude_is_zero(self):
        # clamp_offset(offset) with no amplitude should behave as amplitude=0
        result = sg.clamp_offset(5.0)
        assert result == 5.0


# ===========================================================================
# SECTION 2 — CONNECTION
# ===========================================================================

class TestFindInstruments:
    def test_returns_none_when_no_instruments(self):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ()
        result = sg.find_instruments(mock_rm)
        assert result is None

    def test_returns_tuple_of_addresses(self):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ("USB0::INSTR",)
        result = sg.find_instruments(mock_rm)
        assert result == ("USB0::INSTR",)

    def test_returns_all_addresses(self):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ("USB0::INSTR", "GPIB::5::INSTR")
        result = sg.find_instruments(mock_rm)
        assert len(result) == 2


class TestConnectInstrument:
    def test_opens_resource_at_given_index(self):
        mock_rm = MagicMock()
        instr = make_mock_instrument()
        mock_rm.open_resource.return_value = instr
        addrs = ("USB0::FIRST", "USB0::SECOND")
        sg.connect_instrument(mock_rm, addrs, index=0)
        mock_rm.open_resource.assert_called_once_with("USB0::FIRST")

    def test_selects_correct_index(self):
        mock_rm = MagicMock()
        instr = make_mock_instrument()
        mock_rm.open_resource.return_value = instr
        addrs = ("USB0::FIRST", "USB0::SECOND")
        sg.connect_instrument(mock_rm, addrs, index=1)
        mock_rm.open_resource.assert_called_with("USB0::SECOND")

    def test_sets_10_second_timeout(self):
        mock_rm = MagicMock()
        instr = make_mock_instrument()
        mock_rm.open_resource.return_value = instr
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=0)
        assert result.timeout == 10000

    def test_sets_newline_terminators(self):
        mock_rm = MagicMock()
        instr = make_mock_instrument()
        mock_rm.open_resource.return_value = instr
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=0)
        assert result.read_termination == "\n"
        assert result.write_termination == "\n"


class TestOpenConnection:
    def test_returns_none_when_no_instruments_found(self):
        with patch("sdg_control.connections.pyvisa") as mock_pyvisa:
            mock_rm = MagicMock()
            mock_rm.list_resources.return_value = ()
            mock_pyvisa.ResourceManager.return_value = mock_rm
            result = sg.open_connection()
        assert result is None

    def test_returns_instrument_when_found(self):
        with patch("sdg_control.connections.pyvisa") as mock_pyvisa:
            mock_rm = MagicMock()
            mock_rm.list_resources.return_value = ("USB0::INSTR",)
            instr = make_mock_instrument()
            mock_rm.open_resource.return_value = instr
            mock_pyvisa.ResourceManager.return_value = mock_rm
            result = sg.open_connection()
        assert result is instr


class TestCloseConnection:
    def test_calls_close_on_instrument(self):
        instr = make_mock_instrument()
        sg.close_connection(instr)
        instr.close.assert_called_once()


# ===========================================================================
# SECTION 3 — STATUS QUERIES
# ===========================================================================

class TestGetIdentity:
    def test_sends_idn_query(self):
        instr = make_mock_instrument()
        sg.get_identity(instr)
        instr.query.assert_called_with("*IDN?")

    def test_returns_stripped_identity_string(self):
        instr = make_mock_instrument("SDG,SDG1015,SN123,1.0  ")
        instr.query.return_value = "SDG,SDG1015,SN123,1.0  "
        result = sg.get_identity(instr)
        assert result == "SDG,SDG1015,SN123,1.0"

    def test_returns_string(self):
        instr = make_mock_instrument()
        result = sg.get_identity(instr)
        assert isinstance(result, str)


class TestGetOutputStatus:
    def test_sends_correct_scpi_query(self):
        instr = make_mock_instrument()
        sg.get_output_status(instr, channel=1)
        instr.query.assert_called_with("C1:OUTP?")

    def test_uses_correct_channel(self):
        instr = make_mock_instrument()
        sg.get_output_status(instr, channel=2)
        instr.query.assert_called_with("C2:OUTP?")

    def test_returns_stripped_string(self):
        instr = make_mock_instrument()
        # side_effect in the fixture returns the full instrument reply; override it
        instr.query.side_effect = None
        instr.query.return_value = "C1:OUTP ON,LOAD,HZ,PLRT,NOR  "
        result = sg.get_output_status(instr, channel=1)
        assert result == "C1:OUTP ON,LOAD,HZ,PLRT,NOR"


class TestGetWaveStatus:
    def test_sends_bswv_query(self):
        instr = make_mock_instrument()
        sg.get_wave_status(instr, channel=1)
        instr.query.assert_called_with("C1:BSWV?")

    def test_channel_2_query(self):
        instr = make_mock_instrument()
        sg.get_wave_status(instr, channel=2)
        instr.query.assert_called_with("C2:BSWV?")


# ===========================================================================
# SECTION 4 — OUTPUT CONTROL
# ===========================================================================

class TestTurnOnOutput:
    def test_sends_outp_on_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP ON"
        sg.turn_on_output(instr, channel=1)
        instr.write.assert_called_with("C1:OUTP ON")

    def test_uses_correct_channel(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C2:OUTP ON"
        sg.turn_on_output(instr, channel=2)
        instr.write.assert_called_with("C2:OUTP ON")

    def test_returns_channel_number_on_success(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP ON"
        result = sg.turn_on_output(instr, channel=1)
        assert result == 1

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.turn_on_output(instr, channel=1)
        assert result is None


class TestTurnOffOutput:
    def test_sends_outp_off_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP OFF"
        sg.turn_off_output(instr, channel=1)
        instr.write.assert_called_with("C1:OUTP OFF")

    def test_returns_channel_on_success(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP OFF"
        result = sg.turn_off_output(instr, channel=1)
        assert result == 1

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.turn_off_output(instr, channel=1)
        assert result is None


# ===========================================================================
# SECTION 5 — WAVEFORM PARAMETER SETTERS
# ===========================================================================

class TestSetWaveform:
    def test_sends_correct_scpi_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV WVTP,SINE,FRQ,1000HZ"
        sg.set_waveform(instr, "sine", channel=1)
        instr.write.assert_called_with("C1:BSWV WVTP,SINE")

    def test_square_waveform_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV WVTP,SQUARE"
        sg.set_waveform(instr, "square", channel=1)
        instr.write.assert_called_with("C1:BSWV WVTP,SQUARE")

    def test_returns_lowercase_key_on_success(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV WVTP,SINE"
        result = sg.set_waveform(instr, "SINE", channel=1)
        assert result == "sine"

    def test_returns_none_for_unknown_waveform(self):
        instr = make_mock_instrument()
        result = sg.set_waveform(instr, "triangle", channel=1)
        assert result is None
        instr.write.assert_not_called()

    def test_channel_2_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C2:BSWV WVTP,RAMP"
        sg.set_waveform(instr, "ramp", channel=2)
        instr.write.assert_called_with("C2:BSWV WVTP,RAMP")

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.set_waveform(instr, "sine", channel=1)
        assert result is None

    @pytest.mark.parametrize("waveform", ["sine", "square", "ramp", "pulse", "noise", "arb", "dc"])
    def test_all_valid_waveforms_accepted(self, waveform):
        instr = make_mock_instrument()
        instr.query.return_value = f"C1:BSWV WVTP,{waveform.upper()}"
        result = sg.set_waveform(instr, waveform, channel=1)
        assert result == waveform


class TestSetFrequency:
    def test_sends_frq_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV FRQ,1000HZ"
        sg.set_frequency(instr, 1000.0, channel=1)
        instr.write.assert_called_with("C1:BSWV FRQ,1000.0")

    def test_returns_clamped_frequency(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV FRQ,15000000HZ"
        result = sg.set_frequency(instr, 20e6, channel=1, waveform="sine")
        assert result == 15e6

    def test_clamps_and_sends_clamped_value(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV FRQ,300000HZ"
        sg.set_frequency(instr, 999_999.0, channel=1, waveform="ramp")
        write_cmd = instr.write.call_args[0][0]
        assert "300000.0" in write_cmd

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.set_frequency(instr, 1000.0, channel=1)
        assert result is None


class TestSetAmplitude:
    def test_sends_amp_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV AMP,2V"
        sg.set_amplitude(instr, 2.0, channel=1)
        instr.write.assert_called_with("C1:BSWV AMP,2.0")

    def test_clamps_above_20vpp(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV AMP,20V"
        result = sg.set_amplitude(instr, 25.0, channel=1)
        assert result == 20.0

    def test_clamps_below_2mvpp(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV AMP,0.002V"
        result = sg.set_amplitude(instr, 0.0, channel=1)
        assert result == 0.002

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.set_amplitude(instr, 1.0, channel=1)
        assert result is None


class TestSetOffset:
    def test_sends_ofst_command(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV OFST,1V"
        sg.set_offset(instr, 1.0, amplitude=2.0, channel=1)
        instr.write.assert_called_with("C1:BSWV OFST,1.0")

    def test_clamps_offset_based_on_amplitude(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV OFST,8V"
        result = sg.set_offset(instr, 9.0, amplitude=4.0, channel=1)
        assert result == pytest.approx(8.0)

    def test_max_amplitude_forces_zero_offset(self):
        instr = make_mock_instrument()
        instr.query.return_value = "C1:BSWV OFST,0V"
        result = sg.set_offset(instr, 1.0, amplitude=20.0, channel=1)
        assert result == 0.0

    def test_returns_none_on_visa_error(self):
        import pyvisa
        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = sg.set_offset(instr, 0.0, channel=1)
        assert result is None


# ===========================================================================
# SECTION 6 — CONFIGURE CHANNEL (convenience wrapper)
# ===========================================================================

class TestConfigureChannel:
    def _make_instr(self):
        instr = make_mock_instrument()
        instr.query.side_effect = lambda cmd: {
            "C1:BSWV?":  "C1:BSWV WVTP,SINE,FRQ,1000HZ,AMP,1V,OFST,0V",
            "C1:OUTP?":  "C1:OUTP ON,LOAD,HZ,PLRT,NOR",
        }.get(cmd, "")
        return instr

    def test_returns_dict_with_all_keys(self):
        # No "channel output" key here -- see the module docstring above for
        # why sdg_control's configure_channel() deliberately does not turn
        # the output on or report its state, unlike signal_generator_control.py's.
        instr = self._make_instr()
        result = sg.configure_channel(instr, "sine", 1000.0, 1.0, 0.0, channel=1)
        for key in ("waveform", "frequency", "amplitude", "offset"):
            assert key in result
        assert "channel output" not in result

    def test_waveform_key_is_lowercase(self):
        instr = self._make_instr()
        result = sg.configure_channel(instr, "SINE", 1000.0, 1.0, 0.0, channel=1)
        assert result["waveform"] == "sine"

    def test_frequency_returned_matches_requested(self):
        instr = self._make_instr()
        result = sg.configure_channel(instr, "sine", 5000.0, 1.0, 0.0, channel=1)
        assert result["frequency"] == 5000.0

    def test_amplitude_clamped_above_max(self):
        instr = self._make_instr()
        result = sg.configure_channel(instr, "sine", 1000.0, 25.0, 0.0, channel=1)
        assert result["amplitude"] == 20.0

    def test_channel_2_uses_correct_commands(self):
        instr = make_mock_instrument()
        instr.query.side_effect = lambda cmd: {
            "C2:BSWV?": "C2:BSWV WVTP,SINE,FRQ,1000HZ,AMP,1V,OFST,0V",
            "C2:OUTP?": "C2:OUTP ON",
        }.get(cmd, "")
        sg.configure_channel(instr, "sine", 1000.0, 1.0, 0.0, channel=2)
        written_commands = [c[0][0] for c in instr.write.call_args_list]
        assert all("C2:" in cmd for cmd in written_commands)

    def test_does_not_turn_on_output(self):
        """
        Deliberate divergence from signal_generator_control.py's
        configure_channel(), which does turn the output on internally.
        Here, enabling output is turn_on_output()'s job alone -- callers
        (see complete_pipeline*.py) must call it explicitly.
        """
        instr = self._make_instr()
        sg.configure_channel(instr, "sine", 1000.0, 1.0, 0.0, channel=1)
        written_commands = [c[0][0] for c in instr.write.call_args_list]
        assert "C1:OUTP ON" not in written_commands

    def test_unknown_waveform_still_attempts_remaining_steps(self):
        instr = self._make_instr()
        result = sg.configure_channel(instr, "triangle", 1000.0, 1.0, 0.0, channel=1)
        assert result["waveform"] is None
        # frequency, amplitude, offset should still be attempted
        assert result["frequency"] is not None


# ===========================================================================
# SECTION 7 — ERROR DIAGNOSTICS
# ===========================================================================
# Covers describe_visa_error(), require_instrument() (both in errors.py),
# and every function that (a) rejects instr=None with a specific message
# instead of crashing with AttributeError, and (b) translates a
# pyvisa.VisaIOError into an actionable sentence instead of printing
# pyvisa's generic e.description.
# ===========================================================================

import pyvisa as _pyvisa  # local alias so "pyvisa" stays free for per-test imports above


class TestDescribeVisaError:
    def test_known_error_code_returns_specific_help(self):
        e = _pyvisa.VisaIOError(-1073807339)  # VI_ERROR_TMO
        message = sg_errors.describe_visa_error(e)
        assert "did not respond in time" in message

    def test_resource_not_found_returns_specific_help(self):
        from pyvisa import constants
        e = _pyvisa.VisaIOError(constants.VI_ERROR_RSRC_NFOUND)
        message = sg_errors.describe_visa_error(e)
        assert "no longer reachable" in message

    def test_resource_busy_returns_specific_help(self):
        from pyvisa import constants
        e = _pyvisa.VisaIOError(constants.VI_ERROR_RSRC_BUSY)
        message = sg_errors.describe_visa_error(e)
        assert "already in use" in message

    def test_unrecognised_error_code_falls_back_to_pyvisa_description(self):
        from pyvisa import constants
        e = _pyvisa.VisaIOError(constants.VI_ERROR_NLISTENERS)  # not in our lookup table
        message = sg_errors.describe_visa_error(e)
        assert message == e.description


class TestRequireInstrument:
    def test_none_returns_false_and_explains(self, capsys):
        result = sg_errors.require_instrument(None, "set the frequency")
        assert result is False
        out = capsys.readouterr().out
        assert "set the frequency" in out
        assert "open_connection()" in out

    def test_real_instrument_returns_true_silently(self, capsys):
        instr = make_mock_instrument()
        result = sg_errors.require_instrument(instr, "set the frequency")
        assert result is True
        assert capsys.readouterr().out == ""


class TestFindInstrumentsErrorPaths:
    def test_list_resources_raising_is_caught(self, capsys):
        mock_rm = MagicMock()
        mock_rm.list_resources.side_effect = RuntimeError("backend not started")
        result = sg.find_instruments(mock_rm)
        assert result is None
        out = capsys.readouterr().out
        assert "Could not scan for instruments" in out

    def test_no_instruments_lists_numbered_steps(self, capsys):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ()
        sg.find_instruments(mock_rm)
        out = capsys.readouterr().out
        assert "1. Is the signal generator powered on" in out

    def test_windows_steps_shown_only_on_windows(self, capsys):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ()
        with patch.object(sg_connections, "_ON_WINDOWS", True):
            sg.find_instruments(mock_rm)
        out = capsys.readouterr().out
        assert "Zadig" in out
        assert "libusb-package" in out

    def test_non_windows_steps_hide_windows_instructions(self, capsys):
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ()
        with patch.object(sg_connections, "_ON_WINDOWS", False):
            sg.find_instruments(mock_rm)
        out = capsys.readouterr().out
        assert "Zadig" not in out
        assert "Unplug and replug the USB cable" in out


class TestConnectInstrumentErrorPaths:
    def test_empty_instrs_returns_none(self, capsys):
        mock_rm = MagicMock()
        result = sg.connect_instrument(mock_rm, (), index=0)
        assert result is None
        out = capsys.readouterr().out
        assert "no instrument addresses were given" in out

    def test_index_out_of_range_returns_none(self, capsys):
        mock_rm = MagicMock()
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=5)
        assert result is None
        out = capsys.readouterr().out
        assert "index=5 is out of range" in out
        assert "only 1 instrument" in out
        mock_rm.open_resource.assert_not_called()

    def test_negative_index_returns_none(self, capsys):
        mock_rm = MagicMock()
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=-1)
        assert result is None

    def test_open_resource_visa_error_returns_none(self, capsys):
        mock_rm = MagicMock()
        mock_rm.open_resource.side_effect = _pyvisa.VisaIOError(-1073807339)
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=0)
        assert result is None
        out = capsys.readouterr().out
        assert "did not respond in time" in out

    def test_open_resource_unexpected_error_returns_none(self, capsys):
        mock_rm = MagicMock()
        mock_rm.open_resource.side_effect = ValueError("bad address string")
        result = sg.connect_instrument(mock_rm, ("USB0::A",), index=0)
        assert result is None
        out = capsys.readouterr().out
        assert "Unexpected error" in out
        assert "bad address string" in out


class TestOpenConnectionErrorPaths:
    def test_resource_manager_creation_failure_returns_none(self, capsys):
        with patch("sdg_control.connections.pyvisa.ResourceManager",
                   side_effect=OSError("no VISA library found")):
            result = sg.open_connection()
        assert result is None
        out = capsys.readouterr().out
        assert "Could not start a VISA resource manager" in out
        assert "pip install pyvisa pyvisa-py" in out

    def test_windows_mentions_zadig_on_resource_manager_failure(self, capsys):
        with patch("sdg_control.connections.pyvisa.ResourceManager",
                   side_effect=OSError("no VISA library found")), \
             patch.object(sg_connections, "_ON_WINDOWS", True):
            sg.open_connection()
        out = capsys.readouterr().out
        assert "Zadig" in out


class TestCloseConnectionErrorPaths:
    def test_none_instrument_does_not_crash(self, capsys):
        sg.close_connection(None)  # must not raise
        out = capsys.readouterr().out
        assert "close the connection" in out

    def test_visa_error_on_close_is_caught(self, capsys):
        instr = make_mock_instrument()
        instr.close.side_effect = _pyvisa.VisaIOError(-1073807339)
        sg.close_connection(instr)  # must not raise
        out = capsys.readouterr().out
        assert "did not close cleanly" in out


class TestNoneInstrumentGuards:
    """
    Every function that takes `instr` as its first argument must reject
    None with a specific message and return None, instead of crashing with
    AttributeError deep inside pyvisa. Parametrized over all of them so a
    future function that forgets this guard shows up as a clear failure.
    """

    @pytest.mark.parametrize("call", [
        lambda: sg.get_identity(None),
        lambda: sg.get_output_status(None),
        lambda: sg.get_wave_status(None),
        lambda: sg.turn_on_output(None),
        lambda: sg.turn_off_output(None),
        lambda: sg.set_waveform(None, "sine"),
        lambda: sg.set_frequency(None, 1000.0),
        lambda: sg.set_amplitude(None, 1.0),
        lambda: sg.set_offset(None, 0.0),
    ])
    def test_returns_none_instead_of_crashing(self, call, capsys):
        result = call()
        assert result is None
        out = capsys.readouterr().out
        assert "[ERROR] Cannot" in out
        assert "no instrument is connected" in out

    def test_configure_channel_returns_all_none_dict(self, capsys):
        result = sg.configure_channel(None, "sine", 1000.0, 1.0, 0.0, channel=1)
        assert result == {
            "waveform": None,
            "frequency": None,
            "amplitude": None,
            "offset": None,
        }
        out = capsys.readouterr().out
        # Exactly one guard message, not four (one per sub-call it never made).
        assert out.count("[ERROR] Cannot") == 1


class TestQueryFunctionsVisaErrors:
    def test_get_identity_visa_error_returns_none(self, capsys):
        instr = make_mock_instrument()
        instr.query.side_effect = _pyvisa.VisaIOError(-1073807339)
        result = sg.get_identity(instr)
        assert result is None
        out = capsys.readouterr().out
        assert "Could not read instrument identity" in out

    def test_get_output_status_visa_error_returns_none(self, capsys):
        instr = make_mock_instrument()
        instr.query.side_effect = _pyvisa.VisaIOError(-1073807339)
        result = sg.get_output_status(instr, channel=1)
        assert result is None

    def test_get_wave_status_visa_error_returns_none(self, capsys):
        instr = make_mock_instrument()
        instr.query.side_effect = _pyvisa.VisaIOError(-1073807339)
        result = sg.get_wave_status(instr, channel=1)
        assert result is None
