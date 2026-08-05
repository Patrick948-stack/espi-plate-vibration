"""
run_experiment.py
=================
Author: Patrick Mulikuza
Single entry point for all ESPI experiments so that the user does not have to
deal with the cognitive overload of thinking about the script of every camera.

Simply run this one file it asks you a few questions, runs the sweep,
then shows you the results.

    python3 run_experiment.py

It was designed so that there's no need to edit any code or
know which pipeline file to use.
"""

import os
import sys
import math
import importlib

from settings_manager import load_settings


# ==============================================================================
# ERROR DIAGNOSTICS
# ==============================================================================
# Windows needs an extra Pylon Camera Software Suite install for Basler, and
# a slightly different pip syntax for the Allied Vision wheel file (backslash
# paths). _missing_sdk_message() below is the one place that knows all three
# camera types' install instructions, used by both run_pipeline() (running
# the sweep) and _show_preview_feed() (showing the live preview) so a
# missing SDK always gets the same specific message no matter which of the
# two code paths hits it first.
# ==============================================================================

_ON_WINDOWS = os.name == "nt"


def _missing_sdk_message(camera_choice, module_name, error):
    """
    Print a specific "how to fix this" message for a camera SDK that failed
    to import, tailored to the camera type and (for Allied Vision) to the
    current operating system's file path syntax.

    Args:
        camera_choice : "1" (Basler), "2" (USB/webcam), or "3" (Allied Vision)
        module_name   : the module that failed to import, for the header line
        error         : the exception that was raised (printed for detail)
    """
    print(f"\n[ERROR] Could not load {module_name}: {error}")

    if camera_choice == "1":
        print("  Make sure pypylon is installed: pip install pypylon")
        print("  pypylon also needs the Pylon Camera Software Suite installed")
        print("  separately from basler.com — pip install alone is not enough.")
    elif camera_choice == "2":
        print("  Make sure opencv-python is installed: pip install opencv-python")
    elif camera_choice == "3":
        print("  Make sure vmbpy is installed.")
        print("  Download Vimba X from the Allied Vision website, then find the")
        print("  file ending in .whl inside the installation folder and run:")
        if _ON_WINDOWS:
            print("    pip install C:\\path\\to\\vmbpy_file.whl")
        else:
            print("    pip install /path/to/vmbpy_file.whl")


# ==============================================================================
# HELPERS
# ==============================================================================

def clear():
    """ Wipes the command prompt/ terminal window clean so one can start printing text on an empty screen.
    At first,  it tells Python to temporarily leave its own environment and pass a command directly to the computer's native operating system terminal.
    The message passed is at first to check if the computer runs Windows. Python internally uses the label "nt" to represent Windows operating systems.
    
    If the system is Windows, it chooses the command "cls".
    If the system is Mac or Linux, it chooses the command "clear """

    os.system("cls" if os.name == "nt" else "clear")


def header():
    print("=" * 56)
    print("   ESPI Plate Vibration Python Software")
    print("   Whitman College Prof. Hoffman's Lab")
    print("=" * 56)
    print()


def ask(prompt, default=None, cast=str, valid=None):
    """
    Ask the user a question in the terminal and return their answer.

    This function keeps asking for input until the user provides a valid 
    response that fits the requested type and allowed options.

    Parameters:
    -----------
    prompt : str
        The question or text shown to the user.
    default : any, optional
        The value returned if the user presses Enter without typing anything.
        Defaults to None.
    cast : type, optional
        The data type to convert the answer into (like int, float, or str).
        Defaults to str.
    valid : list or set, optional
        A collection of specific answers that are allowed. If provided,
        the user's answer must match one of these items. Defaults to None.

    Returns:
    --------
    any
        The user's validated and converted answer.
    """
    while True:
        # Show the default choice to the user if one exists
        suffix = f" [default: {default}]" if default is not None else ""
        raw = input(f" {prompt} {suffix}: ").strip()
        
        # Use default if user typed nothing and a default is available
        if raw == "" and default is not None:
            return cast(default)
            
        # Stop empty answers if no default is provided
        if raw == "":
            print(" Please enter a value.")
            continue
            
        # Try to convert the text into the requested data type
        try:
            value = cast(raw)
        except (ValueError, TypeError):
            print(f" That doesn't look right, please enter a {cast.__name__}.")
            continue
            
        # Make sure the answer matches the allowed options if restricted
        if valid and value not in valid:
            print(f" Please enter one of: {', '.join(str(v) for v in valid)}")
            continue
            
        return value



def section(title):
    print()
    print(f"  {title}")
    print("  " + "-" * (len(title) + 2))


def ask_positive_float(prompt, default):
    """
    Like ask(), but also rejects zero and negative numbers.

    ask() already retries until the user types something that converts to a
    float. This wraps that loop with one more check: if the number is not
    greater than zero, explain why and ask again instead of returning it.

    Used anywhere a value must be strictly positive to make physical sense
    (exposure in seconds, gain_factor) — a zero or negative exposure would
    otherwise reach math.log2() deep inside run_pipeline() and crash with
    "math domain error" instead of being caught here, at the moment it was
    typed.

    Example:
        exposure_s = ask_positive_float("Exposure (s)", default=0.01)
    """
    while True:
        value = ask(prompt, default=default, cast=float)
        if value > 0:
            return value
        print(f"  {prompt} must be greater than 0.")


# ==============================================================================
# CAMERA LOOKUP TABLE
# ==============================================================================
# Defined here (not in monitor.py) because monitor.py already imports from
# this file — putting it there and importing it back would create a circular
# import. monitor.py imports this same dict instead of keeping its own copy,
# so the two wizards can never show different names for the same camera.

CAMERA_NAMES = {
    "1": "Basler",
    "2": "USB / webcam (eg. elp camera)",
    "3": "Allied Vision",
}


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

    exposure   = ask_positive_float("Exposure (s)", default=0.01)
    gain       = ask("Gain (dB)", default=0.0, cast=float)

    print()
    print("    gain_factor multiplies each saved difference image so faint")
    print("    fringes are easier to see. Same idea as monitor.py's gain_factor.")
    gain_factor = ask_positive_float("gain_factor", default=1)

    print()
    # An absolute path under the user's home directory, not a bare relative
    # name: a relative default resolves against the process's current
    # working directory, which is wherever the terminal happened to be cd'd
    # to for a from-source run, but is unpredictable (often "/", which is
    # read-only on modern macOS) for the packaged app, launched by double
    # clicking instead of from a terminal. Computed at runtime, not a fixed
    # string, so it resolves to the actual current user's home folder.
    default_output_dir = os.path.join(os.path.expanduser("~"), "Documents", "ESPI Output")
    output_dir = ask("Output folder", default=default_output_dir, cast=str)

    return dict(
        start_freq  = start_freq,
        end_freq    = end_freq,
        step        = step,
        n_averages  = n_averages,
        exposure    = exposure,
        gain        = gain,
        gain_factor = gain_factor,
        output_dir  = output_dir,
    )


def confirm_settings(camera_choice, mode_choice, params):
    mode_names   = {"1": "Pair subtraction", "2": "Reference subtraction"}
    exp_unit     = "s"

    section("Step 4 of 4 — Confirm your settings")
    print()
    print(f"    Camera        :  {CAMERA_NAMES[camera_choice]}")
    print(f"    Mode          :  {mode_names[mode_choice]}")
    print(f"    Frequency     :  {params['start_freq']:g} – "
          f"{params['end_freq']:g} Hz  (step {params['step']:g} Hz)")
    print(f"    Frames/freq   :  {params['n_averages']}")
    print(f"    Exposure      :  {params['exposure']} {exp_unit}")
    print(f"    Gain          :  {params['gain']} dB")
    print(f"    gain_factor   :  {params['gain_factor']}")
    print(f"    Output folder :  {params['output_dir']}")
    print()

    go = ask("Start the experiment? (y/n)", default="y",
             cast=str, valid=["y", "n", "Y", "N"])
    return go.lower() == "y"


# ==============================================================================
# RESULTS VIEWER
# ==============================================================================

def _format_freq_label(freqs):
    """
    Returns a function that formats a frequency with just enough decimal
    places that no two frequencies in the sweep print identically.

    Used by both build_grid_figure() and show_results()'s interactive
    viewer, so a grid subplot title and the paged viewer's title always
    agree on how many decimals to show for the same sweep.
    """
    freq_strs = [f"{round(f, 6):.6f}".rstrip("0") for f in freqs]
    max_dec = max((len(s.split(".")[1]) if "." in s else 0) for s in freq_strs)
    dec = max(0, max_dec)
    return lambda f: f"{f:.{dec}f}"


def build_grid_figure(results, output_dir):
    """
    Build (but do not display) a matplotlib Figure showing every sweep
    result in a grid, and save it to disk.

    This is the pure, display-free half of show_results()'s old grid step —
    split out so run_experiment_gui.py can embed the returned Figure in a
    FigureCanvasQTAgg instead of calling plt.show(), while show_results()
    itself keeps calling this and then opening its usual interactive
    viewer, unchanged.

    Args:
        results    : dict mapping frequency (float, Hz) to an averaged
                     difference image (numpy array), exactly what
                     run_pipeline() returns.
        output_dir : folder the grid PNG is saved into.

    Returns:
        (grid_fig, grid_filename) : the matplotlib Figure (not yet closed)
        and the path it was saved to.
    """
    import matplotlib.pyplot as plt
    from datetime import datetime as _dt

    freqs = sorted(results.keys())
    n = len(freqs)
    fmt = _format_freq_label(freqs)

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
        ax.set_title(f"{fmt(freq)} Hz", fontsize=10)
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

    return grid_fig, grid_filename


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
    _fmt  = _format_freq_label(freqs)

    grid_fig, grid_filename = build_grid_figure(results, output_dir)
    plt.close(grid_fig)
    print(f"\nResults grid saved to: {os.path.abspath(grid_filename)}")

    # ── Interactive viewer: one image at a time ───────────────────────────
    # Wrapped in its own try/except because the grid image above is already
    # saved to disk by this point — a display problem here (no X server on
    # a headless machine, an SSH session without X forwarding, a broken
    # matplotlib GUI backend) should not make it look like the whole sweep
    # failed when the actual measurement data is safe on disk.
    try:
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
    except Exception as e:
        print(f"\n[WARNING] Could not open the interactive viewer: {e}")
        print("  This usually means no display is available (a headless")
        print("  machine, or an SSH session without X forwarding).")
        print(f"  Your results are safe — grid image saved to: "
              f"{os.path.abspath(grid_filename)}")


# ==============================================================================
# PRE-SWEEP: LIVE PREVIEW + RECONFIGURE
# ==============================================================================
# CAMERA_LIBRARY is public (no leading underscore), the same reasoning as
# CAMERA_NAMES above it: run_experiment_gui.py also needs this exact
# camera-choice -> camera_control module mapping to drive its own embedded
# preview and sweep, so it imports this dict instead of keeping its own copy.

CAMERA_LIBRARY = {
    "1": "camera_control",
    "2": "camera_control_inclusive",
    "3": "camera_control_allied_vision",
}


def _show_preview_feed(camera_choice, exposure_s=None, gain=None):
    """
    Open the camera, show a live feed so the user can aim and focus,
    then close the camera.  Press 'e' inside the feed window to continue.

    If exposure_s and/or gain are given, they are locked in before the feed
    opens, using the same per-camera unit conversion run_pipeline() uses
    (seconds -> microseconds for Basler/Allied Vision, log2 scale for a USB
    camera). Without this, the preview shows the camera at whatever exposure
    and gain it already happened to be sitting at — which can look nothing
    like the actual sweep, since the sweep always locks in the settings you
    just typed.  Either argument left as None skips changing that setting.

    Uses importlib to load the right camera library for the chosen camera
    without importing it at module level (avoids crashing when a library
    like pypylon or vmbpy is not installed on the current machine).
    """
    module_name = CAMERA_LIBRARY[camera_choice]

    try:
        cam_lib = importlib.import_module(module_name)
    except ImportError as e:
        # SDK not installed at all — tell them exactly what to install.
        _missing_sdk_message(camera_choice, module_name, e)
        print("  Skipping the live preview; the experiment will still try to run.")
        return

    try:
        connect_camera             = cam_lib.connect_camera
        show_live_feed_from_camera = cam_lib.show_live_feed_from_camera
        disconnect_camera          = cam_lib.disconnect_camera
    except AttributeError as e:
        # The module imported fine but is missing an expected function —
        # a different problem from "not installed": the file itself is
        # incomplete, out of date, or was edited and something got deleted.
        print(f"\n  [WARNING] {module_name}.py imported but is missing a "
              f"function it should have: {e}")
        print(f"  Check that {module_name}.py has not been partially edited "
              f"or is an outdated copy, then skipping the live preview.")
        return

    section("Camera preview")
    print()
    print("    Aim and focus the camera at the plate.")
    print("    Press 'e' to close the feed and continue.")
    print()

    result = connect_camera()
    if result is None or (isinstance(result, tuple) and result[0] is None):
        print("  [WARNING] Could not open camera — skipping preview.")
        return
    camera, format_info = result

    if exposure_s is not None or gain is not None:
        try:
            set_exposure_manual = cam_lib.set_exposure_manual
            set_gain_manual     = cam_lib.set_gain_manual
            if exposure_s is not None:
                # Camera 2 (USB/webcam) takes a log2 scale, not seconds —
                # the same conversion run_pipeline() applies before the sweep.
                exposure_value = math.log2(exposure_s) if camera_choice == "2" \
                                  else exposure_s * 1_000_000
                set_exposure_manual(camera, exposure_value)
            if gain is not None:
                set_gain_manual(camera, gain)
        except Exception as e:
            print(f"  [WARNING] Could not apply exposure/gain to the preview: {e}")
            print("  Continuing with the camera's current settings instead.")

    try:
        show_live_feed_from_camera(camera)
    except Exception as e:
        # The preview is a convenience, not a requirement — a crash here
        # (e.g. the USB cable came loose while aiming) should not stop the
        # whole program from continuing on to the actual experiment.
        print(f"\n  [WARNING] Camera preview stopped unexpectedly: {e}")
        print("  Continuing without the preview.")
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
            params["exposure"]    = ask_positive_float("Exposure (s)", default=params["exposure"])
            params["gain"]        = ask("Gain (dB)",    default=params["gain"],    cast=float)
            params["gain_factor"] = ask_positive_float("gain_factor", default=params["gain_factor"])

        if choice in ("signal", "both"):
            section("Signal generator settings")
            print()
            params["start_freq"] = ask("Start frequency (Hz)", default=params["start_freq"], cast=float)
            params["end_freq"]   = ask("End frequency   (Hz)", default=params["end_freq"],   cast=float)
            params["step"]       = ask("Step size       (Hz)", default=params["step"],       cast=float)
            params["n_averages"] = ask("Frames per frequency", default=params["n_averages"], cast=int)

        _show_preview_feed(camera_choice, params["exposure"], params["gain"])

        section("Updated settings")
        print()
        print(f"    Frequency  :  {params['start_freq']:g} – "
              f"{params['end_freq']:g} Hz  (step {params['step']:g} Hz)")
        print(f"    Frames/freq:  {params['n_averages']}")
        print(f"    Exposure   :  {params['exposure']} s")
        print(f"    Gain       :  {params['gain']} dB")
        print(f"    gain_factor:  {params['gain_factor']}")
        print()

        again = ask("Change anything else? (y/n)", default="n", cast=str, valid=["y", "n"])
        if again == "n":
            return params


# ==============================================================================
# PIPELINE RUNNER
# ==============================================================================

def run_pipeline(camera_choice, mode_choice, params, stop_check=None):
    """
    Import the right pipeline and call the right function.

    stop_check : optional callable forwarded straight through to whichever
                 sweep function is chosen. Checked once per frequency, before
                 any hardware command for that frequency — see
                 complete_pipeline.py's frequency_sweep() docstring for the
                 full explanation. Left as None (the default) for every
                 existing terminal caller, which never stops early.
    """

    exposure    = params["exposure"]
    gain        = params["gain"]
    gain_factor = params["gain_factor"]
    output_dir  = params["output_dir"]
    # .get() with the same 1.0/0.0 every sweep function already defaults
    # to, since run_experiment.py's own terminal CLI (choose_sweep_params())
    # does not collect these yet — only run_experiment_gui.py's SetupPage does.
    amplitude   = params.get("amplitude", 1.0)
    offset      = params.get("offset", 0.0)

    # Read from the same settings file run_experiment_gui.py's _start_preview()
    # already reads, so the real Sweep captures with the exact grayscale
    # method/color the user sees in Preview, instead of always connecting
    # the camera in its default "standard" mode.
    settings           = load_settings()
    grayscale_method    = settings.get("grayscale_method", "standard")
    grayscale_color     = settings.get("grayscale_color", "R")

    base_params = dict(
        start_freq        = params["start_freq"],
        end_freq          = params["end_freq"],
        step              = params["step"],
        n_averages        = params["n_averages"],
        gain              = gain,
        gain_factor       = gain_factor,
        amplitude         = amplitude,
        offset            = offset,
        output_dir        = output_dir,
        stop_check        = stop_check,
        grayscale_method  = grayscale_method,
        grayscale_color   = grayscale_color,
    )

    # ---- Basler ----
    if camera_choice == "1":
        try:
            from complete_pipeline import (
                frequency_sweep,
                reference_frequency_sweep,
            )
        except ImportError as e:
            _missing_sdk_message(camera_choice, "complete_pipeline", e)
            return None

        exposure_us = exposure * 1000000    #convert exposure time from seconds to microseconds
        p = {**base_params, "exposure_us": exposure_us}
        sweep_fn = reference_frequency_sweep if mode_choice == "2" else frequency_sweep

    # ---- OpenCV / any USB camera ----
    elif camera_choice == "2":
        try:
            from complete_pipeline_inclusive import (
                frequency_sweep_inclusive,
                reference_frequency_sweep_inclusive,
            )
        except ImportError as e:
            _missing_sdk_message(camera_choice, "complete_pipeline_inclusive", e)
            return None

        try:
            exp_log_scale = math.log2(exposure)
        except ValueError:
            print(f"\n[ERROR] Invalid exposure: {exposure} s. Exposure must be "
                  f"greater than 0 (0.01 s = 10 ms is a good starting point).")
            return None

        p = {**base_params, "exposure": exp_log_scale, "skip_live_feed": True}
        sweep_fn = reference_frequency_sweep_inclusive if mode_choice == "2" \
                   else frequency_sweep_inclusive

    # ---- Allied Vision ----
    elif camera_choice == "3":
        try:
            from complete_pipeline_allied_vision import (
                frequency_sweep_allied_vision,
                reference_frequency_sweep_allied_vision,
            )
        except ImportError as e:
            _missing_sdk_message(camera_choice, "complete_pipeline_allied_vision", e)
            return None

        exposure_us = exposure * 1000000
        p = {**base_params, "exposure_us": exposure_us, "skip_live_feed": True}
        sweep_fn = reference_frequency_sweep_allied_vision if mode_choice == "2" \
                   else frequency_sweep_allied_vision

    else:
        print(f"\n[ERROR] Unknown camera choice: {camera_choice!r}")
        return None

    try:
        return sweep_fn(**p)
    except Exception as e:
        # A crash here means the import and setup all succeeded, but
        # something failed during the actual sweep — most often the signal
        # generator or camera disconnecting partway through. Report it
        # instead of letting a raw traceback end the whole program.
        print(f"\n[ERROR] The experiment stopped unexpectedly: {e}")
        print("  Check that the camera and signal generator are still")
        print("  connected and powered on, then try running the sweep again.")
        return None


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    try:
        _run()
    except KeyboardInterrupt:
        # Ctrl+C is a normal, intentional way to back out of any of the
        # questions above — it is not a bug, so it should end quietly
        # instead of showing a raw traceback that looks like a crash.
        print("\n\n  Cancelled (Ctrl+C). No experiment was started.")
        sys.exit(0)


def _run():
    clear()
    header()

    camera_choice = choose_camera()
    mode_choice   = choose_mode()
    params        = choose_sweep_params()

    if not confirm_settings(camera_choice, mode_choice, params):
        print("\n  Experiment cancelled.")
        sys.exit(0)

    _show_preview_feed(camera_choice, params["exposure"], params["gain"])

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

