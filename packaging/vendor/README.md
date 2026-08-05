# Vendored packages

`vmbpy-1.2.2-py3-none-any.whl` is the Python wheel for Allied Vision's
`vmbpy` camera bindings, from their Vimba X SDK. It is not on PyPI, so it
cannot be installed with a plain `pip install vmbpy`, only from this
exact file (or an equivalent one obtained the same way, by installing
Vimba X and finding it under `api/python/` in the install folder).

It is checked into this repo, rather than left as something every build
has to go find on its own, so `packaging/requirements-build.txt` can
install it the same way as every other build dependency, and so the
GitHub Actions Windows build can bundle Allied Vision support into
`ESPI.exe` without needing the full Vimba X SDK installed on the CI
runner. Confirmed safe to redistribute this way: it is licensed BSD
2-Clause (`vmbpy-LICENSE.txt` alongside it, copied from the wheel's own
`dist-info` folder, satisfying that license's requirement that the
notice travel with any redistributed copy), and unpacking the wheel
shows it contains only pure Python source, no compiled binaries.

This wheel is only half of what Allied Vision camera support actually
needs. It provides the Python bindings, which is all PyInstaller can
bundle into the app file. The other half, the real Vimba X Runtime
(camera drivers, GenTL producer files), is not in this wheel, is not
redistributed here, and still has to be installed separately by anyone
who wants to actually connect an Allied Vision camera, exactly the same
way the Basler pylon Runtime does. See
`.claude/pyinstaller-packaging-plan.md` for the full explanation.

This exact file was obtained straight from the
[VmbPy GitHub Releases page](https://github.com/alliedvision/VmbPy/releases)
(the Assets list under a release), not by installing the full Vimba X
SDK. A separate 1.0.4 copy pulled from an actual local Vimba X install
was tried first and worked identically in a trial build, confirming both
routes produce the same kind of file; 1.2.2 was kept since it is newer,
and the wheel's own `py3-none-any` tag means the file itself carries no
platform-specific code either way, Windows or Mac, despite where it came
from.

If a newer version ever needs to replace this file, either route works:
install Vimba X and find `vmbpy-<version>-py3-none-any.whl` under its own
`api/python/` folder, or download the wheel directly from the GitHub
Releases page above. Either way, copy both the wheel and its
`LICENSE.txt` here in place of these, and update the version number in
`packaging/requirements-build.txt`.
