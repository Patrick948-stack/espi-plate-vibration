"""
run_experiment.py
=================
Single entry point for all ESPI experiments.

Just run this one file — it asks you a few questions, runs the sweep,
then shows you the results.

    python3 run_experiment.py

It was designed so that there's no need to edit any code or
know which pipeline file to use.
"""

import os
import sys
import math
import importlib


# ==============================================================================
# HELPERS
# ==============================================================================

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def header():
    print("=" * 56)
    print("   ESPI Plate Vibration Python Software")
    print("   Whitman College Prof. Hoffman's Lab")
    print("=" * 56)
    print()


def ask(prompt, default=None, cast=str, valid=None):
    """
    Print a prompt, wait for input, and return the typed value.

    - If the user presses Enter without typing, the default is used.
    - If valid is given, the answer must be one of those values.
    - If cast is given, the answer is converted to that type (e.g. float, int).
    """
    while True:
        suffix = f"  [default: {default}]" if default is not None else ""
        raw = input(f"  {prompt} {suffix}: ").strip()

        if raw == "" and default is not None:
            return cast(default)

        if raw == "":
            print("  Please enter a value.")
            continue

        try:
            value = cast(raw)
        except (ValueError, TypeError):
            print(f"  That doesn't look right, please enter a {cast.__name__}.")
            continue

        if valid and value not in valid:
            print(f"  Please enter one of: {', '.join(str(v) for v in valid)}")
            continue

        return value


def section(title):
    print()
    print(f"  {title}")
    print("  " + "-" * (len(title) + 2))


# ==============================================================================
# STEP-BY-STEP QUESTIONS
# ==============================================================================

def choose_camera():
    section("Step 1 of 4 — Which camera are you using? Enter the camera number from the list below.")
    print("    1.  Basler camera")
    print("    2.  USB webcam or any other camera (such as ELP Camera)")
    print("    3.  Allied Vision camera (Vimba X)")
    print()
    return ask("Enter choice", default="2", cast=str, valid=["1", "2", "3"])


def choose_mode():
    section("Step 2 of 4 — Which subtraction method?")
    print()
    print("    1.  Pair subtraction")
    print("        Two frames are grabbed at each frequency and subtracted")
    print("        from each other.")
    print()
    print("    2.  Reference subtraction")
    print("        One frame is captured with the plate at rest.  Every")
    print("        measurement frame is then compared to that baseline.")
    print()
    return ask("Enter choice", default="1", cast=str, valid=["1", "2"])


def choose_sweep_params():
    section("Step 3 of 4 — Frequency sweep settings")
    print()

    start_freq = ask("Start frequency (Hz)", default=100,  cast=float)
    end_freq   = ask("End frequency   (Hz)", default=1000, cast=float)
    step       = ask("Step size       (Hz)", default=100,  cast=float)
    n_averages = ask("Frames per frequency", default=5,    cast=int)

    print()
    print("    Exposure is in SECONDS.")
    print("    0.01 = 10 ms (good starting point).")
    print("    Increase if the image is too dark; decrease if too bright.")

    exposure   = ask("Exposure (s)", default=0.01, cast=float)
    gain       = ask("Gain (dB)", default=0.0, cast=float)

    print()
    output_dir = ask("Output folder", default="output", cast=str)

    return dict(
        start_freq = start_freq,
        end_freq   = end_freq,
        step       = step,
        n_averages = n_averages,
        exposure   = exposure,
        gain       = gain,
        output_dir = output_dir,
    )


def confirm_settings(camera_choice, mode_choice, params):
    camera_names = {"1": "Basler", "2": "USB / webcam", "3": "Allied Vision"}
    mode_names   = {"1": "Pair subtraction", "2": "Reference subtraction"}
    exp_unit     = "s"

    section("Step 4 of 4 — Confirm your settings")
    print()
    print(f"    Camera        :  {camera_names[camera_choice]}")
    print(f"    Mode          :  {mode_names[mode_choice]}")
    print(f"    Frequency     :  {params['start_freq']:g} – "
          f"{params['end_freq']:g} Hz  (step {params['step']:g} Hz)")
    print(f"    Frames/freq   :  {params['n_averages']}")
    print(f"    Exposure      :  {params['exposure']} {exp_unit}")
    print(f"    Gain          :  {params['gain']} dB")
    print(f"    Output folder :  {params['output_dir']}")
    print()

    go = ask("Start the experiment? (y/n)", default="y",
             cast=str, valid=["y", "n", "Y", "N"])
    return go.lower() == "y"


# ==============================================================================
# RESULTS VIEWER
# ==============================================================================

def show_results(results, output_dir):
    """
    Save a full grid of all sweep images to disk, then open an interactive
    viewer that shows one image at a time.

    Use ← → arrow keys (or Space) to navigate between images.
    Press Escape to close the viewer.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping results display.")
        print(f"Images are saved in: {os.path.abspath(output_dir)}")
        return

    if not results:
        print("No results to display.")
        return

    freqs = sorted(results.keys())
    n     = len(freqs)

    # Determine how many decimal places to show so no frequency looks the same.
    _freq_strs = [f"{round(f, 6):.6f}".rstrip("0") for f in freqs]
    _max_dec   = max(
        (len(s.split(".")[1]) if "." in s else 0) for s in _freq_strs
    )
    _dec = max(0, _max_dec)

    def _fmt(f):
        return f"{f:.{_dec}f}"

    # ── Save the full grid to disk (no window) ────────────────────────────
    from datetime import datetime as _dt
    ncols = min(4, n)
    nrows = (n + ncols - 1) // ncols
    grid_fig, axes = plt.subplots(nrows, ncols,
                                  figsize=(ncols * 3.5, nrows * 3.5),
                                  squeeze=False)
    grid_fig.suptitle("ESPI Sweep Results", fontsize=14, fontweight="bold")
    for i, freq in enumerate(freqs):
        row, col = divmod(i, ncols)
        ax = axes[row][col]
        ax.imshow(results[freq], cmap="gray", interpolation="nearest")
        ax.set_title(f"{_fmt(freq)} Hz", fontsize=10)
        ax.axis("off")
    for j in range(n, nrows * ncols):
        row, col = divmod(j, ncols)
        axes[row][col].set_visible(False)
    grid_fig.tight_layout()
    grid_filename = os.path.join(
        output_dir,
        f"sweep_results_{_dt.now().strftime('%Y-%m-%d_%H%M%S')}.png",
    )
    grid_fig.savefig(grid_filename, dpi=150, bbox_inches="tight")
    plt.close(grid_fig)
    print(f"\nResults grid saved to: {os.path.abspath(grid_filename)}")

    # ── Interactive viewer: one image at a time ───────────────────────────
    fig, ax = plt.subplots(figsize=(7, 7))
    idx = [0]

    fig.text(
        0.5, 0.01,
        "← → (or Space) to navigate   ·   Escape to close",
        ha="center", fontsize=9, color="gray",
        transform=fig.transFigure,
    )

    def _draw(i):
        ax.clear()
        freq = freqs[i]
        ax.imshow(results[freq], cmap="gray", interpolation="nearest")
        ax.set_title(f"{_fmt(freq)} Hz   ({i + 1} / {n})",
                     fontsize=13, fontweight="bold")
        ax.axis("off")
        fig.canvas.draw_idle()

    def _on_key(event):
        if event.key in ("right", " "):
            idx[0] = min(idx[0] + 1, n - 1)
            _draw(idx[0])
        elif event.key == "left":
            idx[0] = max(idx[0] - 1, 0)
            _draw(idx[0])
        elif event.key == "escape":
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", _on_key)
    _draw(0)
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    print("Viewer open — ← → arrow keys (or Space) to navigate, Escape to close.")
    plt.show()


# ==============================================================================
# PRE-SWEEP: LIVE PREVIEW + RECONFIGURE
# ==============================================================================

_CAMERA_LIBRARY = {
    "1": "camera_control",
    "2": "camera_control_inclusive",
    "3": "camera_control_allied_vision",
}


def _show_preview_feed(camera_choice):
    """
    Open the camera, show a live feed so the user can aim and focus,
    then close the camera.  Press 'e' inside the feed window to continue.

    Uses importlib to load the right camera library for the chosen camera
    without importing it at module level (avoids crashing when a library
    like pypylon or vmbpy is not installed on the current machine).
    """
    module_name = _CAMERA_LIBRARY[camera_choice]

    try:
        cam_lib                  = importlib.import_module(module_name)
        connect_camera           = cam_lib.connect_camera
        show_live_feed_from_camera = cam_lib.show_live_feed_from_camera
        disconnect_camera        = cam_lib.disconnect_camera
    except (ImportError, AttributeError):
        print("\n  [WARNING] Camera library unavailable — skipping preview.")
        return

    section("Camera preview")
    print()
    print("    Aim and focus the camera at the plate.")
    print("    Press 'e' to close the feed and continue.")
    print()

    camera = connect_camera()
    if camera is None:
        print("  [WARNING] Could not open camera — skipping preview.")
        return

    try:
        show_live_feed_from_camera(camera)
    finally:
        disconnect_camera(camera)


def reconfigure_if_needed(camera_choice, params):
    """
    Ask the user whether they want to adjust camera or signal generator
    settings before the sweep starts.  Loops until they are done.

    Returns the (possibly updated) params dict.
    """
    while True:
        section("Pre-sweep adjustment")
        print()

        choice = ask(
            "Adjust settings before starting? (camera / signal / both / no)",
            default="no",
            cast=str,
            valid=["camera", "signal", "both", "no"],
        )

        if choice == "no":
            return params

        if choice in ("camera", "both"):
            section("Camera settings")
            print()
            print("    Exposure is in SECONDS.  0.01 = 10 ms.")
            print("    Increase if the image was too dark; decrease if too bright.")
            print()
            params["exposure"] = ask("Exposure (s)", default=params["exposure"], cast=float)
            params["gain"]     = ask("Gain (dB)",    default=params["gain"],    cast=float)

        if choice in ("signal", "both"):
            section("Signal generator settings")
            print()
            params["start_freq"] = ask("Start frequency (Hz)", default=params["start_freq"], cast=float)
            params["end_freq"]   = ask("End frequency   (Hz)", default=params["end_freq"],   cast=float)
            params["step"]       = ask("Step size       (Hz)", default=params["step"],       cast=float)
            params["n_averages"] = ask("Frames per frequency", default=params["n_averages"], cast=int)

        _show_preview_feed(camera_choice)

        section("Updated settings")
        print()
        print(f"    Frequency  :  {params['start_freq']:g} – "
              f"{params['end_freq']:g} Hz  (step {params['step']:g} Hz)")
        print(f"    Frames/freq:  {params['n_averages']}")
        print(f"    Exposure   :  {params['exposure']} s")
        print(f"    Gain       :  {params['gain']} dB")
        print()

        again = ask("Change anything else? (y/n)", default="n", cast=str, valid=["y", "n"])
        if again == "n":
            return params


# ==============================================================================
# PIPELINE RUNNER
# ==============================================================================

def run_pipeline(camera_choice, mode_choice, params):
    """Import the right pipeline and call the right function."""

    exposure   = params["exposure"]
    gain       = params["gain"]
    output_dir = params["output_dir"]

    base_params = dict(
        start_freq = params["start_freq"],
        end_freq   = params["end_freq"],
        step       = params["step"],
        n_averages = params["n_averages"],
        gain       = gain,
        output_dir = output_dir,
    )

    # ---- Basler ----
    if camera_choice == "1":
        try:
            from complete_pipeline import (
                frequency_sweep,
                reference_frequency_sweep,
            )
        except ImportError as e:
            print("\n[ERROR] Could not import the Basler pipeline.")
            print(f"  Details: {e}")
            print("  Make sure pypylon is installed:  pip install pypylon")
            return None

        exposure_us = exposure * 1000000    #convert exposure time from seconds to microseconds
        p = {**base_params, "exposure_us": exposure_us}
        return reference_frequency_sweep(**p) if mode_choice == "2" \
               else frequency_sweep(**p)

    # ---- OpenCV / any USB camera ----
    elif camera_choice == "2":
        try:
            from complete_pipeline_inclusive import (
                frequency_sweep_inclusive,
                reference_frequency_sweep_inclusive,
            )
        except ImportError as e:
            print("\n[ERROR] Could not import the OpenCV pipeline.")
            print(f"  Details: {e}")
            print("  Make sure opencv-python is installed: "
                  "pip install opencv-python")
            return None
        
        exp_log_scale = math.log2(exposure)

        p = {**base_params, "exposure": exp_log_scale, "skip_live_feed": True}
        return reference_frequency_sweep_inclusive(**p) if mode_choice == "2" \
               else frequency_sweep_inclusive(**p)

    # ---- Allied Vision ----
    elif camera_choice == "3":
        try:
            from complete_pipeline_allied_vision import (
                frequency_sweep_allied_vision,
                reference_frequency_sweep_allied_vision,
            )
        except ImportError as e:
            print("\n[ERROR] Could not import the Allied Vision pipeline.")
            print(f"  Details: {e}")
            print("  Make sure vmbpy is installed.")
            print("  Download from: https://github.com/alliedvision/VmbPy")
            print("  Then run: pip install <downloaded_wheel>.whl")
            return None
        exposure_us = exposure * 1000000
        p = {**base_params, "exposure_us": exposure_us, "skip_live_feed": True}
        return reference_frequency_sweep_allied_vision(**p) if mode_choice == "2" \
               else frequency_sweep_allied_vision(**p)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    clear()
    header()

    camera_choice = choose_camera()
    mode_choice   = choose_mode()
    params        = choose_sweep_params()

    if not confirm_settings(camera_choice, mode_choice, params):
        print("\n  Experiment cancelled.")
        sys.exit(0)

    _show_preview_feed(camera_choice)

    while True:
        params = reconfigure_if_needed(camera_choice, params)
        if confirm_settings(camera_choice, mode_choice, params):
            break

    print()
    print("=" * 56)
    print("  Starting experiment — do not unplug any cables.")
    print("=" * 56)
    print()

    results = run_pipeline(camera_choice, mode_choice, params)

    print()
    if results:
        print(f"  Done. {len(results)} frequency/frequencies measured.")
        print(f"  Images saved to: {os.path.abspath(params['output_dir'])}")
        show_results(results, params["output_dir"])
    else:
        print("  No results were collected.")
        print("  Check the error messages above for details.")


if __name__ == "__main__":
    main()

