"""
test_sdg_control_constants.py
Tests for sdg_control/constants.py — the single source of truth for
hardware settling-time constants, shared by output.py (relay settling)
and waveform.py (parameter-change settling), replacing what used to be a
duplicated `COMMAND_SETTLE_S = 0.2` defined locally inside waveform.py.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestConstants:
    def test_command_settle_is_defined_and_reasonable(self):
        from sdg_control.constants import COMMAND_SETTLE_S

        assert COMMAND_SETTLE_S > 0
        assert COMMAND_SETTLE_S < 1.0

    def test_output_settle_is_defined_and_reasonable(self):
        from sdg_control.constants import OUTPUT_SETTLE_S

        assert OUTPUT_SETTLE_S > 0
        assert OUTPUT_SETTLE_S < 1.0

    def test_output_settle_greater_than_command_settle(self):
        """A relay physically moving takes longer than an electronic parameter change."""
        from sdg_control.constants import COMMAND_SETTLE_S, OUTPUT_SETTLE_S

        assert OUTPUT_SETTLE_S > COMMAND_SETTLE_S

    def test_waveform_module_uses_the_shared_constant(self):
        """waveform.py must import COMMAND_SETTLE_S rather than redefine it."""
        from sdg_control.constants import COMMAND_SETTLE_S
        from sdg_control import waveform

        assert waveform.COMMAND_SETTLE_S == COMMAND_SETTLE_S

    def test_package_exports_both_constants(self):
        import sdg_control

        assert sdg_control.COMMAND_SETTLE_S > 0
        assert sdg_control.OUTPUT_SETTLE_S > 0
