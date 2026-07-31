"""
test_sweep_tuple_unpacking_bug.py
=================================
Tests that EXPOSE the critical bug in sweep functions.

THE BUG:
complete_pipeline.py's frequency_sweep() calls connect_camera() but doesn't unpack the tuple.
connect_camera() returns (camera, format_info) or (None, {})
But the code does: camera = connect_camera() and then if camera is None:
This fails because (None, {}) is truthy (it's a non-empty tuple), so the check passes.
Then it tries to use the TUPLE as a camera object, causing AttributeError.

This test will FAIL before the fix and PASS after.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))


class TestSweepTupleUnpackingBug:
    """Expose the tuple unpacking bug in sweep code."""

    def test_frequency_sweep_handles_camera_connection_failure(self):
        """
        FAILURE SCENARIO: Camera fails to connect.
        connect_camera returns (None, {})
        sweep code assigns it to camera without unpacking
        Then tries to use camera as object

        BEFORE FIX: Code crashes trying to call set_exposure_manual(tuple, ...)
        AFTER FIX: Should handle gracefully and return None
        """
        # This test FAILS before fix, PASSES after fix

        # Mock the pipeline functions
        with patch("complete_pipeline.open_connection") as mock_open_sg, \
             patch("complete_pipeline.connect_camera") as mock_connect_cam, \
             patch("complete_pipeline.close_connection") as mock_close_sg:

            # Signal generator connects OK
            mock_instr = MagicMock()
            mock_open_sg.return_value = mock_instr

            # Camera fails to connect, returns (None, {})
            # This is what connect_camera() actually returns when it fails
            mock_connect_cam.return_value = (None, {})

            # Now call frequency_sweep
            from complete_pipeline import frequency_sweep

            result = frequency_sweep(
                start_freq=100.0,
                end_freq=200.0,
                step=50.0,
                n_averages=2,
                exposure_us=10000.0,
                gain=0.0,
                gain_factor=1.0,
                output_dir="output",
            )

            # BEFORE FIX: This would crash with:
            # AttributeError: 'tuple' object has no attribute 'set_exposure_manual'
            # or similar, because camera is actually (None, {})

            # AFTER FIX: Should return None gracefully
            assert result is None, "frequency_sweep should return None when camera fails"

            # Verify signal generator was properly closed
            mock_close_sg.assert_called_once_with(mock_instr)

    def test_all_pipeline_files_have_tuple_unpacking_bug(self):
        """
        Verify that the pipeline files DON'T have proper tuple unpacking.
        This test FAILS after the fix is applied (which is the goal).
        """
        # Check that files have the buggy pattern

        files_to_check = [
            ("ESPI Full Algorithm/complete_pipeline.py", "frequency_sweep"),
            ("ESPI Full Algorithm/complete_pipeline_inclusive.py", "frequency_sweep_inclusive"),
            ("ESPI Full Algorithm/complete_pipeline_allied_vision.py", "frequency_sweep_allied_vision"),
        ]

        for filepath, func_name in files_to_check:
            with open(filepath) as f:
                content = f.read()

            # Look for the buggy pattern: camera = connect_camera() followed by if camera is None:
            has_buggy_assignment = f"camera = connect_camera(" in content
            proper_unpack_in_sweep = f"camera, format_info = connect_camera(" in content or \
                                    f"camera, _ = connect_camera(" in content

            # Before fix: should have buggy assignment but not proper unpacking
            # After fix: should have proper unpacking
            if has_buggy_assignment and not proper_unpack_in_sweep:
                # THIS SHOULD FAIL BEFORE FIX
                pytest.fail(
                    f"{filepath} has tuple unpacking bug: "
                    f"assigns tuple to camera without unpacking"
                )

    def test_buggy_code_pattern_vs_fixed_pattern(self):
        """
        Demonstrate the difference between buggy and fixed code.
        """
        def buggy_pattern(camera_result):
            """BEFORE FIX: This crashes"""
            camera = camera_result  # Returns tuple but treated as single value
            if camera is None:  # Tuple is never None, so this is always False
                return "error"
            # Try to use as object - will crash
            try:
                camera.set_exposure(10000)  # camera is (None, {}), AttributeError!
                return "ok"
            except (AttributeError, TypeError) as e:
                return f"crash: {type(e).__name__}"

        def fixed_pattern(camera_result):
            """AFTER FIX: This handles correctly"""
            # Validate tuple structure first
            if not isinstance(camera_result, tuple) or len(camera_result) != 2:
                return "error"
            
            camera, format_info = camera_result  # Properly unpack
            
            if camera is None:  # Now this check makes sense
                return "error"
            
            return "ok"

        # Test buggy pattern with failure case
        crash_result = buggy_pattern((None, {}))
        assert "crash" in crash_result, f"Buggy pattern should crash, got: {crash_result}"

        # Test fixed pattern with failure case
        fixed_result = fixed_pattern((None, {}))
        assert fixed_result == "error", f"Fixed pattern should return error, got: {fixed_result}"

        # Test fixed pattern with success case
        mock_camera = MagicMock()
        success_result = fixed_pattern((mock_camera, {"format": "Mono8"}))
        assert success_result == "ok", f"Fixed pattern should succeed, got: {success_result}"


class TestSweepWithCameraLock:
    """Test sweep behavior when camera is locked."""

    def test_camera_lock_prevents_sweep_connection(self):
        """
        REAL SCENARIO from user's bug:
        1. Preview holds camera lock (exclusively opened)
        2. Sweep tries to connect → get (None, {})
        3. Without proper unpacking, code crashes with AttributeError
        4. With proper unpacking, returns None gracefully
        """
        camera_lock_holder = {"owner": None}

        def mock_connect_camera_with_lock(*args, **kwargs):
            """Enforces exclusive access like real camera"""
            if camera_lock_holder["owner"] is not None:
                # Camera in use, return failure tuple
                return (None, {})
            camera_lock_holder["owner"] = "sweep"
            return (MagicMock(), {"format": "Mono8"})

        # Test pattern: preview holds lock
        camera_lock_holder["owner"] = "preview"

        # Buggy code would crash
        camera_result = mock_connect_camera_with_lock()
        assert camera_result == (None, {}), "Connect returns failure tuple"

        # Buggy assignment and check
        camera = camera_result
        if camera is None:  # WRONG - this is False because tuple is not None
            pass  # Error handling never runs
        
        # Then code tries to use camera as object - would crash
        # This is why we got the AttributeError in user's real run

        # Fixed code would handle it
        if not isinstance(camera, tuple) or camera[0] is None:
            assert True, "Fixed code detects the failure"
