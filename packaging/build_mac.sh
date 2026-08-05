#!/usr/bin/env bash
# Mac build script for the ESPI app.
#
# Why this script exists, not just the raw pyinstaller command: every Mac
# build so far produced an app with a BROKEN code signature, not just an
# unsigned one. PyInstaller's own automatic signing step failed silently
# during the build:
#
#   WARNING: Error while signing the bundle: codesign command (...) failed
#   with error code 1!
#   output: ESPI.app: replacing existing signature
#   ESPI.app: resource fork, Finder information, or similar detritus not
#   allowed
#
# This was invisible when testing locally right after a build, since a
# freshly built app has no com.apple.quarantine attribute and macOS skips
# its strict Gatekeeper signature check for non-quarantined apps. It only
# surfaced once the app was downloaded through a browser (which sets that
# quarantine attribute), at which point macOS showed "'ESPI' is damaged
# and can't be opened. You should move it to the Trash." instead of the
# milder, expected "developer cannot be verified" prompt.
#
# THE REAL ROOT CAUSE, found the hard way: this project's folder lives
# under this Mac's iCloud Drive Desktop sync. `xattr -cr` (strip extended
# attributes, then sign) looked like the fix and is what every guide
# recommends, but it does not work here: macOS's iCloud file-provider
# daemon re-tags every file in a synced folder with its own extended
# attributes (com.apple.fileprovider.fpfs#P, com.apple.provenance,
# com.apple.FinderInfo) continuously in the background, independent of
# anything this script does. Confirmed directly: running `xattr -cr` on
# the built .app, then checking again a couple of seconds later, showed
# the same attributes had already come back on their own. `codesign`
# always loses that race if it runs anywhere inside a synced folder,
# no matter how quickly it follows the `xattr -cr` call.
#
# THE FIX: do the entire build, sign, and verify sequence inside a plain
# temp directory (via mktemp -d), which is never iCloud-synced, so
# nothing re-tags it mid-build. Only the final, already-signed-and-zipped
# result is copied back into packaging/dist/ afterward, purely for local
# convenience; the zip itself is inert data by that point; whatever
# happens to a loose copy of ESPI.app sitting in this synced folder
# afterward cannot change what is already inside the zip.
#
# Usage, from the project root, with venv_physics active:
#   bash packaging/build_mac.sh

set -euo pipefail

cd "$(dirname "$0")/.."   # project root, regardless of where this is run from
PROJECT_ROOT="$(pwd)"

FINAL_DIST="packaging/dist"

# Everything below happens in a temp dir OUTSIDE this iCloud-synced
# project folder. This is the actual fix, see the header above.
BUILD_TMP="$(mktemp -d)"
echo "== Building in a non-iCloud-synced temp dir: $BUILD_TMP =="
trap 'rm -rf "$BUILD_TMP"' EXIT

APP="$BUILD_TMP/dist/ESPI.app"
ZIP="$BUILD_TMP/dist/ESPI-mac.zip"

echo "== Running PyInstaller (packaging/ESPI.spec) =="
pyinstaller packaging/ESPI.spec \
    --distpath "$BUILD_TMP/dist" \
    --workpath "$BUILD_TMP/build"

echo "== Stripping extended attributes that block codesign =="
xattr -cr "$APP"

echo "== Signing (ad hoc: no paid Developer ID certificate for this project) =="
codesign --force --deep --sign - "$APP"

echo "== Verifying the signature actually took =="
if ! codesign --verify --verbose "$APP"; then
    echo "FAILED: signature verification did not pass. Do not zip or ship this build." >&2
    exit 1
fi

echo "== Simulating a real download (quarantine flag) as a best-effort extra check =="
# A freshly built, non-quarantined app passes Gatekeeper's basic check even
# with a broken signature, which is exactly how this bug shipped in v1.0.0
# undetected. Setting the same quarantine attribute Safari/Chrome set on a
# real download, then launching it the way a user's double click would
# (via `open`), is the closest local simulation of that available.
#
# This check is informational, not a hard gate (unlike codesign --verify
# above): confirmed against this exact build_mac.sh output, this
# open-and-check-for-a-process test was flaky when driven from an
# automated shell (timing sensitive, sometimes reports no process even
# on a build later confirmed, by an actual human double-clicking the
# real downloaded zip, to open correctly with only the expected mild
# "Apple could not verify... free of malware" prompt). Do not treat a
# failure here alone as proof the build is bad; do treat a
# `codesign --verify` failure above as proof it is.
#
# Also note: `spctl --assess --type execute` on this same quarantined app
# reports "rejected" even on a fully working build, and that is EXPECTED:
# spctl's static assessment requires real Apple notarization (a paid
# Apple Developer Program membership this project does not have) to ever
# say "accepted" at all. That is a separate, known, accepted limitation
# (see packaging/INSTALL.md's "right-click, Open" / "Open Anyway"
# instructions), not the "damaged, move to Trash" bug this script exists
# to catch; that bug specifically came from a BROKEN signature removing
# the right-click/Open Anyway override entirely, which codesign --verify
# above already rules out.
xattr -w com.apple.quarantine "0081;00000000;Safari;" "$APP"
open "$APP" 2>/dev/null || true
sleep 3
if pgrep -f "ESPI.app/Contents/MacOS/ESPI" > /dev/null; then
    echo "Launched successfully under a simulated quarantine flag."
    pkill -f "ESPI.app/Contents/MacOS/ESPI" || true
    sleep 1
else
    echo "NOTE: could not confirm the process launched from this automated shell (see comment above; this has been flaky here even on known-good builds). The codesign --verify pass above is the authoritative check. Still do one real end-to-end test (upload, download via an actual browser, double-click in Finder) before considering this build fully confirmed."
fi
xattr -d com.apple.quarantine "$APP" 2>/dev/null || true

echo "== Zipping for distribution (still inside the non-synced temp dir) =="
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "== Copying the finished build back into packaging/dist/ =="
mkdir -p "$FINAL_DIST"
rm -rf "${FINAL_DIST:?}/ESPI.app" "$FINAL_DIST/ESPI-mac.zip"
cp -R "$APP" "$FINAL_DIST/ESPI.app"
cp "$ZIP" "$FINAL_DIST/ESPI-mac.zip"

echo ""
echo "Build OK."
echo "  Zip (the actual artifact to distribute): $FINAL_DIST/ESPI-mac.zip"
echo "  App (local copy, for convenience only):  $FINAL_DIST/ESPI.app"
echo ""
echo "Note: the local ESPI.app copy above now sits back inside this"
echo "iCloud-synced project folder and may re-acquire the same extended"
echo "attributes over time. That is harmless for the zip already built"
echo "(it was signed and verified before ever leaving the temp dir), but"
echo "do not re-sign or re-verify the loose .app copy in place; re-run"
echo "this whole script instead if you need a fresh signed build."
echo ""
echo "Before publishing, it is still worth one real end-to-end test:"
echo "upload $FINAL_DIST/ESPI-mac.zip, download it through an actual"
echo "browser, and open that downloaded copy."
