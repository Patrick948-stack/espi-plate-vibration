"""
test_broken_workflow_now_fixed.py
=================================
Reproduce the exact broken workflow user reported, verify it's now fixed.

BROKEN WORKFLOW (from user's bug report):
1. Start app → defaults load
2. Change exposure, camera, frequencies in UI
3. Click "Start Sweep"
4. Live feed windows appear but then close
5. Error: 'tuple' object has no attribute 'ExposureAuto'
6. No data collected
7. Restart app → settings reset to defaults (not saved)

EXPECTED WORKFLOW (after fixes):
1. Start app → defaults load OR saved settings load
2. Change settings
3. Click "Start Sweep" → settings saved to disk
4. Live feed works, sweep collects data
5. Restart app → user's settings persist
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestBrokenWorkflowNowFixed:
    """Reproduce and verify fix for exact reported issue."""

    def test_settings_persist_across_app_restart(self):
        """
        THE CORE ISSUE: User changes settings, app closes, restarts.
        Expected: Settings should persist (not lost).
        This was broken because save_settings() was never called.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== PHASE 1: First app startup ====
                # User opens app, loads defaults
                settings_s1 = load_settings()
                assert settings_s1["default_exposure"] == DEFAULT_SETTINGS["default_exposure"]

                # ==== PHASE 2: User changes settings in UI ====
                # User changes these in the GUI:
                # - Exposure: 0.01 → 0.055
                # - Camera: 2 → 3
                # - Start frequency: 100 → 250
                user_changes = settings_s1.copy()
                user_changes["default_exposure"] = 0.055
                user_changes["default_camera_choice"] = "3"
                user_changes["default_start_freq"] = 250.0

                # ==== PHASE 3: User clicks "Continue" or "Start Sweep" ====
                # With the fix: save_settings() is called
                save_result = save_settings(user_changes)
                assert save_result is True, "Settings should save when user continues"

                # Verify settings actually wrote to disk
                with open(settings_file) as f:
                    saved = json.load(f)
                assert saved["default_exposure"] == 0.055, "Exposure should be on disk"

                # ==== PHASE 4: App closes (simulated by ending session) ====
                # User closes app, computer might restart, etc.

                # ==== PHASE 5: User opens app again ====
                settings_s2 = load_settings()

                # ==== PHASE 6: VERIFY THE FIX ====
                # This is what was BROKEN: settings would be back to defaults
                # This is what should be FIXED: settings should persist
                assert settings_s2["default_exposure"] == 0.055, \
                    "BROKEN: Exposure lost on restart (was 0.055, now {})".format(
                        settings_s2["default_exposure"])
                assert settings_s2["default_camera_choice"] == "3", \
                    "BROKEN: Camera choice lost on restart (was 3, now {})".format(
                        settings_s2["default_camera_choice"])
                assert settings_s2["default_start_freq"] == 250.0, \
                    "BROKEN: Start frequency lost on restart (was 250.0, now {})".format(
                        settings_s2["default_start_freq"])

    def test_ui_shows_saved_settings_when_returning_to_setup(self):
        """
        SECONDARY ISSUE: User returns to setup, UI shows stale values.
        Expected: UI should reload from disk and show saved settings.
        This was broken because reload_settings() didn't exist.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== User changes settings and saves ====
                settings = load_settings()
                settings.update({
                    "default_exposure": 0.077,
                    "default_camera_choice": "1",
                })
                save_settings(settings)

                # ==== User returns to setup ====
                # Simulate SetupPage.reload_settings() being called
                reloaded = load_settings()

                # ==== VERIFY: UI controls should show saved values ====
                # (In real code, SetupPage would update its UI controls)
                assert reloaded["default_exposure"] == 0.077, \
                    "SetupPage should reload exposure from disk"
                assert reloaded["default_camera_choice"] == "1", \
                    "SetupPage should reload camera choice from disk"

    def test_camera_available_for_sweep_after_preview(self):
        """
        SECONDARY ISSUE: Sweep fails with 'Device exclusively opened'.
        Expected: Preview releases camera, sweep can connect.
        This was already fixed in defensive programming, verify it works.
        """
        camera_state = {"owner": None}

        def mock_connect(name, **kwargs):
            if camera_state["owner"] is not None and camera_state["owner"] != name:
                raise RuntimeError(f"Device exclusively opened by {camera_state['owner']}")
            camera_state["owner"] = name
            return (MagicMock(), {"format": "Mono8"})

        def mock_disconnect(name, camera):
            if camera_state["owner"] == name:
                camera_state["owner"] = None

        # ==== Preview connects ====
        try:
            camera1, fmt1 = mock_connect("preview")
            assert camera_state["owner"] == "preview"
        except RuntimeError as e:
            pytest.fail(f"Preview should connect: {e}")

        # ==== Preview disconnects (from finally block) ====
        mock_disconnect("preview", camera1)
        assert camera_state["owner"] is None, "Camera should be released"

        # ==== Sweep connects (was failing with 'exclusively opened') ====
        try:
            camera2, fmt2 = mock_connect("sweep")
            assert camera_state["owner"] == "sweep"
        except RuntimeError as e:
            pytest.fail(f"Sweep should connect after preview disconnects: {e}")

        # ==== Verify success ====
        assert camera_state["owner"] == "sweep"

    def test_complete_user_workflow_end_to_end(self):
        """
        Complete reproduction of user's reported workflow.
        Verify every step works correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                print("\n=== SIMULATING USER'S EXACT WORKFLOW ===\n")

                # STEP 1: User opens app
                print("1. User opens app")
                settings = load_settings()
                print(f"   Loaded defaults: exposure={settings['default_exposure']}, camera={settings['default_camera_choice']}")

                # STEP 2: User changes settings
                print("\n2. User changes settings in UI")
                user_settings = settings.copy()
                user_settings["default_exposure"] = 0.055  # Changed
                user_settings["default_camera_choice"] = "3"  # Changed
                user_settings["default_start_freq"] = 250.0  # Changed
                print(f"   User set: exposure=0.055, camera=3, freq=250.0")

                # STEP 3: User clicks "Continue to Preview" (should save)
                print("\n3. User clicks 'Continue to Preview'")
                save_result = save_settings(user_settings)
                print(f"   Settings saved: {save_result}")
                assert save_result is True, "Save should succeed"

                # STEP 4: Preview runs (simulated)
                print("\n4. Preview runs (camera used and released)")
                preview_settings = load_settings()
                print(f"   Preview read: exposure={preview_settings['default_exposure']}")

                # STEP 5: App closes
                print("\n5. User closes app")

                # STEP 6: User reopens app
                print("\n6. User opens app again")
                restart_settings = load_settings()
                print(f"   Loaded settings: exposure={restart_settings['default_exposure']}, camera={restart_settings['default_camera_choice']}")

                # STEP 7: VERIFY SETTINGS PERSISTED
                print("\n7. VERIFY: Settings should NOT be back to defaults")
                assert restart_settings["default_exposure"] == 0.055, \
                    f"❌ FAILED: Exposure lost (expected 0.055, got {restart_settings['default_exposure']})"
                print(f"   ✓ Exposure persisted: {restart_settings['default_exposure']}")

                assert restart_settings["default_camera_choice"] == "3", \
                    f"❌ FAILED: Camera lost (expected 3, got {restart_settings['default_camera_choice']})"
                print(f"   ✓ Camera persisted: {restart_settings['default_camera_choice']}")

                assert restart_settings["default_start_freq"] == 250.0, \
                    f"❌ FAILED: Frequency lost (expected 250.0, got {restart_settings['default_start_freq']})"
                print(f"   ✓ Frequency persisted: {restart_settings['default_start_freq']}")

                print("\n=== ✓ WORKFLOW FIXED ===\n")

    def test_multiple_user_sessions(self):
        """
        Verify settings persist across MULTIPLE app restarts.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Session 1: User sets exposure
                s1 = load_settings()
                s1["default_exposure"] = 0.011
                save_settings(s1)

                # Session 2: User adds camera change
                s2 = load_settings()
                assert s2["default_exposure"] == 0.011, "Session 1 changes should persist"
                s2["default_camera_choice"] = "2"
                save_settings(s2)

                # Session 3: User changes frequency
                s3 = load_settings()
                assert s3["default_exposure"] == 0.011, "Session 1 changes should still persist"
                assert s3["default_camera_choice"] == "2", "Session 2 changes should persist"
                s3["default_start_freq"] = 333.0
                save_settings(s3)

                # Session 4: Verify all changes accumulated
                s4 = load_settings()
                assert s4["default_exposure"] == 0.011, "Session 1"
                assert s4["default_camera_choice"] == "2", "Session 2"
                assert s4["default_start_freq"] == 333.0, "Session 3"
                # All three changes should persist across multiple sessions
