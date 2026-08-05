# Installing the ESPI App

These instructions are for someone who was just given the packaged app
file (`ESPI.exe` on Windows, or `ESPI-mac.zip` on Mac) and wants to run
it. There is no installer to run and nothing to build. If you are
setting up the project from source code instead, see the main
`README.md` in the project root, not this file.

Two things stay true no matter which computer you're on:

- The app itself needs no separate Python install and no `pip install`
  step. Everything it needs is already inside the one file you were
  given.
- The camera still needs its own separate driver software installed
  once per computer, from whichever camera company made it (Basler or
  Allied Vision). This is a real physical driver for the hardware, not
  something that can be bundled into the app file, so this one step
  cannot be skipped no matter how the app is packaged.

---

## Windows

1. **Get the file.** You should have one file, `ESPI.exe`. Save it
   somewhere easy to find, like your Desktop or Documents folder. No
   installer, no admin rights needed for this step.

2. **Double-click `ESPI.exe`.**

3. **Windows will likely show a blue warning screen** that says
   "Windows protected your PC". This is expected. It happens because
   this app was not purchased through the Microsoft Store and does not
   have a paid code-signing certificate, not because anything is wrong
   with it. Click **More info**, then click **Run anyway**. You should
   only see this once. Running as Administrator, or any other permission
   change, will not make this warning go away; "More info" then "Run
   anyway" is the actual, complete fix for it.

4. The app should now open to its main landing page, with a Monitor
   option and a Scan option.

5. **If you have a Basler camera:** go to basler.com, search for "pylon
   Camera Software Suite", and install the full Software Suite (not the
   smaller "Runtime" download, it is missing pieces this app needs) for
   Windows. Run its installer normally.

6. **If you have an Allied Vision camera:** go to alliedvision.com and
   install the Vimba X SDK for Windows. **The version matters, not just
   "any Vimba X install":** this app was built with the Python bindings
   from vmbpy version 1.2.2, which checks the installed SDK's native
   library version the moment the app tries to use it, and refuses to
   work with a mismatched one instead of just working anyway. Install
   the Vimba X SDK release that corresponds to VmbPy 1.2.2 (check the
   version list on the
   [VmbPy GitHub Releases page](https://github.com/alliedvision/VmbPy/releases)
   if the SDK installer's own version number does not obviously match).
   If Allied Vision mode still does not work after installing some
   version of Vimba X, this mismatch is the first thing to check, not a
   sign the app itself is broken.

7. **If you are also using the signal generator** (for the Scan/sweep
   mode, not just Monitor mode), one extra one-time step is needed on
   Windows specifically: a small free tool called Zadig has to bind the
   right USB driver to it once. Full step-by-step instructions for this
   are in `ESPI Full Algorithm/requirements.txt` in the project source,
   under the "Zadig driver step" section. This step is Windows-only;
   Mac does not need it.

8. Open `ESPI.exe` again (or leave it open from step 4) and try
   Monitor mode with your camera selected. If a live picture appears,
   everything is working.

**If something does not work**, and you have Python available on that
same Windows computer, `packaging/windows_diagnostic.py` from the
project source can check exactly which of the steps above did not take,
instead of guessing:
```
python packaging\windows_diagnostic.py
```

---

## Mac

1. **Get the file.** You should have `ESPI-mac.zip`.

2. **Double-click the zip file** to unzip it. This produces `ESPI.app`.

3. **Move `ESPI.app` somewhere you'll remember it**, most simply your
   Applications folder (drag it there) or just leave it on your
   Desktop. Either is fine, this app does not need to live in
   Applications to work.

4. **Double-click `ESPI.app` to open it.** The first time, macOS will
   likely refuse, usually with "Apple could not verify 'ESPI' is free of
   malware that may harm your Mac or compromise your privacy" (older
   macOS versions phrase the same block as "cannot be opened because the
   developer cannot be verified" instead; both mean the same thing).
   This is expected, for the same reason as the Windows warning above:
   no paid Apple Developer Program membership behind this app, so it is
   not Apple-notarized. Work around it with either of these (only needed
   once):
   - **Right-click (or Control-click) the app, choose Open, then click
     Open again** in the dialog that appears. On some macOS versions
     this is all that's needed.
   - **If that dialog does not offer an Open option** (common on newer
     macOS versions), go to **System Settings > Privacy & Security**,
     scroll down, and you should see a line naming `ESPI` as blocked,
     with an **Open Anyway** button next to it. Click it, then confirm
     once more (you may be asked for your password or Touch ID) in the
     dialog that follows.

5. The app should now open to its main landing page.

6. **The first time you use Monitor mode with a camera**, macOS will
   show its own separate permission prompt asking whether ESPI can
   access your camera. Click **Allow**. If you click "Don't Allow" by
   mistake, you can turn it back on later in System Settings > Privacy
   & Security > Camera.

7. **If you have a Basler camera:** go to basler.com, search for "pylon
   Camera Software Suite", and install the full Software Suite for Mac
   (Basler does provide a Mac version).

8. **If you have an Allied Vision camera:** install the Vimba X SDK for
   Mac from alliedvision.com. **The version matters here too, and Mac
   needs an older one than Windows.** This Mac build uses the Python
   bindings from vmbpy version 1.0.4, not the newer 1.2.2 used for the
   Windows build, because Allied Vision's newer SDK releases (the ones
   matching newer vmbpy versions) are Windows and Linux focused, and the
   native runtime version 1.2.2 expects was not available for Mac at the
   time this app was built. Install the Vimba X SDK release that
   corresponds to VmbPy 1.0.4 specifically (check the version list on the
   [VmbPy GitHub Releases page](https://github.com/alliedvision/VmbPy/releases)
   if needed), not whatever the newest Mac download happens to be.

9. The signal generator needs no extra Zadig-style driver step on Mac,
   USB access already works without it.

10. Try Monitor mode with your camera selected. If a live picture
    appears, everything is working.
