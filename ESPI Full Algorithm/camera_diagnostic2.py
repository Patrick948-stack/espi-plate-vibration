import cv2
import time

# ==============================================================================
# WHAT THIS SCRIPT IS FOR
# ==============================================================================
# The first run of this script (mirroring the real app's exact sequence: open,
# then set exposure and gain, THEN start reading) measured a real USB webcam
# needing about 3.4 seconds before its first successful read(), and caught the
# camera dropping frames again briefly after that, well after the initial
# warm-up had already succeeded.
#
# The retry fix in camera_control_inclusive.py now uses that 3.4 second
# measurement to size a 6.0 second retry budget (see monitor_gui.py's
# DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S). What is still missing is how long
# those mid-session drops actually last. This run is longer (about 60 seconds
# instead of 6) and prints a clear summary at the end instead of raw per-
# attempt spam, specifically:
#   - how long the initial warm-up took
#   - every failure streak seen AFTER the warm-up, with its start time and
#     duration
#
# Run this with the real camera plugged in and paste the summary back.
# ==============================================================================

NUM_ATTEMPTS = 200          # about 60 seconds at 0.3s between reads
POLL_INTERVAL_S = 0.3

cap = cv2.VideoCapture(0)
print("isOpened:", cap.isOpened())

cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cap.set(cv2.CAP_PROP_EXPOSURE, -4.3)
actual_exposure = cap.get(cv2.CAP_PROP_EXPOSURE)
print(f"Exposure set to: {actual_exposure} (requested -4.3)")

cap.set(cv2.CAP_PROP_GAIN, 1.0)
actual_gain = cap.get(cv2.CAP_PROP_GAIN)
print(f"Gain set to: {actual_gain} (requested 1.0)")

print(f"Now reading frames every {POLL_INTERVAL_S}s for {NUM_ATTEMPTS} attempts "
      f"(about {NUM_ATTEMPTS * POLL_INTERVAL_S:.0f} seconds total)...")

start = time.time()
warmup_end_s = None          # elapsed time of the first successful read
streaks = []                 # list of (start_s, end_s) for post-warmup failure runs
current_streak_start = None

for i in range(NUM_ATTEMPTS):
    ok, frame = cap.read()
    elapsed = time.time() - start
    print(f"attempt {i + 1} at {elapsed:.1f}s: ok={ok}, frame is None={frame is None}"
          + (f", shape={frame.shape}" if frame is not None else ""))

    if ok:
        if warmup_end_s is None:
            warmup_end_s = elapsed
        elif current_streak_start is not None:
            streaks.append((current_streak_start, elapsed))
            current_streak_start = None
    else:
        if warmup_end_s is not None and current_streak_start is None:
            current_streak_start = elapsed

    time.sleep(POLL_INTERVAL_S)

# A failure streak still in progress when the loop ended has no known end time.
if current_streak_start is not None:
    streaks.append((current_streak_start, None))

cap.release()

print("\n===== SUMMARY =====")
if warmup_end_s is None:
    print("Camera never produced a successful frame in this run.")
else:
    print(f"Initial warm-up: first successful read() at {warmup_end_s:.1f}s")

if not streaks:
    print("No failures seen after the initial warm-up.")
else:
    print(f"{len(streaks)} failure streak(s) after warm-up:")
    for streak_start, streak_end in streaks:
        if streak_end is None:
            print(f"  started at {streak_start:.1f}s, still failing when the run ended")
        else:
            duration = streak_end - streak_start
            print(f"  {streak_start:.1f}s to {streak_end:.1f}s (about {duration:.1f}s)")
