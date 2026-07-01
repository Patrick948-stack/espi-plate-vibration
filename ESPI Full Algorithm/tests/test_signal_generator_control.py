"""
test_signal_generator_control.py
Tests for signal_generator_control.py (Siglent SDG1015 via pyvisa).

Sections covered
----------------
  
    clamp_frequency, clamp_amplitude, clamp_offset

  Hardware functions (pyvisa.ResourceManager mocked):
    find_instruments, connect_instrument, open_connection, close_connection,
    get_identity, get_output_status, get_wave_status,
    turn_on_output, turn_off_output,
    set_waveform, set_frequency, set_amplitude, set_offset,
    configure_channel
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import signal_generator_control as sg

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

    # --- Too-low values are clamped to 1 µHz minimum ---
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
        # amplitude=4 Vpp → peaks swing ±2 V → max offset = 10 - 2 = 8 V
        assert sg.clamp_offset(5.0, amplitude=4.0) == 5.0

    def test_negative_offset_within_range(self):
        assert sg.clamp_offset(-5.0, amplitude=4.0) == -5.0

    def test_offset_clamped_when_above_limit(self):
        # amplitude=4 Vpp, max offset = 8 V; request 9 V → clamped to 8 V
        result = sg.clamp_offset(9.0, amplitude=4.0)
        assert result == pytest.approx(8.0)

    def test_offset_clamped_when_below_negative_limit(self):
        result = sg.clamp_offset(-9.0, amplitude=4.0)
        assert result == pytest.approx(-8.0)

    def test_max_amplitude_forces_zero_offset(self):
        # 20 Vpp → peaks swing ±10 V → offset must be 0
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
        result = sg.connect_instrument(mock_rm, addrs, index=0)
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
        with patch("signal_generator_control.pyvisa") as mock_pyvisa:
            mock_rm = MagicMock()
            mock_rm.list_resources.return_value = ()
            mock_pyvisa.ResourceManager.return_value = mock_rm
            result = sg.open_connection()
        assert result is None

    def test_returns_instrument_when_found(self):
        with patch("signal_generator_control.pyvisa") as mock_pyvisa:
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
        instr = self._make_instr()
        result = sg.configure_channel(instr, "sine", 1000.0, 1.0, 0.0, channel=1)
        for key in ("waveform", "frequency", "amplitude", "offset", "channel output"):
            assert key in result

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

    def test_turns_on_output(self):
        instr = self._make_instr()
        sg.configure_channel(instr, "sine", 1000.0, 1.0, 0.0, channel=1)
        written_commands = [c[0][0] for c in instr.write.call_args_list]
        assert "C1:OUTP ON" in written_commands

    def test_unknown_waveform_still_attempts_remaining_steps(self):
        instr = self._make_instr()
        result = sg.configure_channel(instr, "triangle", 1000.0, 1.0, 0.0, channel=1)
        assert result["waveform"] is None
        # frequency, amplitude, offset should still be attempted
        assert result["frequency"] is not None
