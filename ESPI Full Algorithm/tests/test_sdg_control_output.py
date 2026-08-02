"""
test_sdg_control_output.py
Tests for sdg_control/output.py — turn_on_output() and turn_off_output().

sdg_control/output.py is currently empty, which makes the whole sdg_control
package unimportable: sdg_control/__init__.py already does
`from .output import turn_on_output, turn_off_output` at import time. So
these tests double as a regression check that `import sdg_control` itself
no longer raises ImportError.

Behavior matches the existing, already-tested signal_generator_control.py
implementation exactly (see tests/test_signal_generator_control.py's
TestTurnOnOutput/TestTurnOffOutput): both functions return the channel
number (int) on success, not a status string, and None on a
pyvisa.VisaIOError. No instr-is-None guard, matching the rest of
sdg_control's own modules (waveform.py, status.py), which trust the caller
to pass an already-open connection.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pyvisa

from conftest import make_mock_instrument


class TestSdgControlImportable:
    def test_import_sdg_control_does_not_raise(self):
        import sdg_control  # noqa: F401 -- the point of this test is that it imports cleanly


class TestTurnOnOutput:
    def test_sends_outp_on_command(self):
        from sdg_control.output import turn_on_output

        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP ON"
        turn_on_output(instr, channel=1)
        instr.write.assert_called_with("C1:OUTP ON")

    def test_uses_correct_channel(self):
        from sdg_control.output import turn_on_output

        instr = make_mock_instrument()
        instr.query.return_value = "C2:OUTP ON"
        turn_on_output(instr, channel=2)
        instr.write.assert_called_with("C2:OUTP ON")

    def test_returns_channel_number_on_success(self):
        from sdg_control.output import turn_on_output

        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP ON"
        result = turn_on_output(instr, channel=1)
        assert result == 1

    def test_returns_none_on_visa_error(self):
        from sdg_control.output import turn_on_output

        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = turn_on_output(instr, channel=1)
        assert result is None


class TestTurnOffOutput:
    def test_sends_outp_off_command(self):
        from sdg_control.output import turn_off_output

        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP OFF"
        turn_off_output(instr, channel=1)
        instr.write.assert_called_with("C1:OUTP OFF")

    def test_returns_channel_on_success(self):
        from sdg_control.output import turn_off_output

        instr = make_mock_instrument()
        instr.query.return_value = "C1:OUTP OFF"
        result = turn_off_output(instr, channel=1)
        assert result == 1

    def test_returns_none_on_visa_error(self):
        from sdg_control.output import turn_off_output

        instr = make_mock_instrument()
        instr.write.side_effect = pyvisa.VisaIOError(-1073807339)
        result = turn_off_output(instr, channel=1)
        assert result is None
