# Installation and troubleshooting

Archlence is distributed as an active pre-release. It is suitable for testing
and development, but it is not yet recommended as the sole store for everyday
financial records. Keep a verified backup before installing an update or using
real data.

## Choose an installation method

| Platform | Recommended method | Python required | Desktop integration |
| --- | --- | --- | --- |
| Windows | Per-user installer | No | Start menu and optional desktop shortcut |
| Arch, Manjaro, CachyOS | `archlence-bin` package | No | Application menu, icon, and terminal command |
| Other x86-64 Linux | AppImage | No | Portable application |
| macOS | Source installation | Yes | No packaged release |

Published packages are available from the
[latest GitHub release](https://github.com/superuser-d0/archlence/releases/latest).
Do not clone the repository when using the Windows installer or AppImage.

## Release files and verification

A tagged release can contain:

- `ArchlenceSetup-<version>.exe` — Windows per-user installer;
- `Archlence-<version>-x86_64.AppImage` — portable x86-64 Linux package;
- `SHA256SUMS.txt` — package checksums;
- `Archlence-<version>-sbom.cdx.json` — CycloneDX software bill of materials;
- `THIRD_PARTY_NOTICES.md` — bundled third-party notices.

Packages are unsigned. A checksum can detect an incomplete or altered download,
but it does not provide the publisher identity assurance of code signing.
Download the package and `SHA256SUMS.txt` from the same release.

### Verify a Windows installer

Open PowerShell in a clean download directory containing one installer and the
checksum file:

```powershell
$installer = Get-ChildItem .\ArchlenceSetup-*.exe | Select-Object -First 1
$pattern = [regex]::Escape($installer.Name) + '$'
$expected = (Select-String -Path .\SHA256SUMS.txt -Pattern $pattern).Line.Split()[0]
$actual = (Get-FileHash $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "Checksum verification failed" }
```

If no matching line is found, do not run the installer. Confirm that both files
came from the same release.

### Verify a Linux AppImage

Open a terminal in a clean download directory containing one Archlence
AppImage and the checksum file:

```bash
sha256sum --ignore-missing -c SHA256SUMS.txt
chmod +x Archlence-*-x86_64.AppImage
./Archlence-*-x86_64.AppImage
```

The checksum command must report `OK` for the AppImage you intend to run.

## Windows installer

1. Download the installer and `SHA256SUMS.txt` from the latest release.
2. Verify the installer as described above.
3. Run the installer.
4. Open Archlence from the Start menu.

The installer is per-user, does not request administrator privileges, and
installs under `%LOCALAPPDATA%\Programs\Archlence`. The desktop shortcut is
optional.

The installer is not code-signed, so Windows SmartScreen may warn on first
launch. Verify the checksum before choosing **More info → Run anyway**. If the
download does not match the published checksum, delete it and do not bypass the
warning.

On first launch, Archlence guides you through creating a local password and the
initial account.

### Upgrade and remove on Windows

Run the newer installer for an in-place application upgrade. The packaged
upgrade checks in CI exercise preservation of a previous-release profile, but
pre-release users should still create and verify a backup first.

Remove Archlence from Windows **Installed apps** or its Start-menu uninstaller.
Upgrade and uninstall do not intentionally remove the user database. If you
want to remove financial records, use the application's data controls before
uninstalling and retain a backup only if you intend to restore it later.

## Arch-based Linux package

The repository includes a `PKGBUILD` for the prebuilt AppImage. Build it as a
normal user:

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
makepkg -si
```

Do not run `makepkg` with `sudo`; it asks for the administrator password only
for the final Pacman installation. The package installs the application under
`/opt/archlence`, an application-menu entry, scalable (SVG) and
high-resolution (PNG) system icons, and the `/usr/bin/archlence` launcher.

```bash
archlence
pacman -Qi archlence-bin
```

The package is not currently published in the AUR. To update from an existing
clean checkout after a new release:

```bash
cd ~/archlence
git status
git pull --ff-only
makepkg -si
```

Commit or stash your own changes before pulling. Remove the package with:

```bash
sudo pacman -R archlence-bin
```

Package removal does not intentionally delete per-user application data.

## AppImage on other Linux distributions

The AppImage targets x86-64 Linux. It is not an ARM package. Download and
verify it, make it executable, and run it using the commands in the verification
section.

If the system needs the FUSE 2 runtime, install the distribution package:

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install libfuse2

# Fedora
sudo dnf install fuse

# Arch, Manjaro, CachyOS
sudo pacman -S --needed fuse2
```

When FUSE mounting is unavailable, use the AppImage extraction fallback:

```bash
./Archlence-*-x86_64.AppImage --appimage-extract-and-run
```

## Run from source

Source setup is intended for development, macOS, or testing unreleased `main`
code. Use Python 3.11 or newer. CI and packaged builds currently use Python
3.12.

### Linux system dependencies

```bash
# Debian, Ubuntu, Linux Mint
sudo apt update
sudo apt install git python3 python3-venv python3-pip \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libsdl2-mixer-2.0-0 libgl1

# Fedora
sudo dnf install git python3 python3-pip SDL2 SDL2_image SDL2_ttf SDL2_mixer mesa-libGL

# Arch, Manjaro, CachyOS
sudo pacman -S --needed git python python-pip sdl2-compat sdl2_image sdl2_ttf sdl2_mixer libglvnd
```

### Linux and macOS

On macOS, install `python@3.12` and Git with Homebrew, then use `python3.12`
in place of `python3`. macOS has no packaged, signed, or notarized release and
is not a current packaged support target.

```bash
git clone https://github.com/superuser-d0/archlence.git
cd archlence
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-runtime.txt
.venv/bin/python main.py
```

Virtual-environment activation is optional. If you prefer activation:

```bash
# POSIX shells such as bash or zsh
source .venv/bin/activate

# Fish
source .venv/bin/activate.fish
```

### Windows source setup

```powershell
git clone https://github.com/superuser-d0/archlence.git
cd archlence
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-runtime.txt
.venv\Scripts\python.exe -m pip install kivy_deps.sdl2 kivy_deps.glew kivy_deps.angle
.venv\Scripts\python.exe main.py
```

PowerShell activation is optional. If execution policy blocks `Activate.ps1`,
continue using `.venv\Scripts\python.exe` directly instead of changing the
machine-wide policy.

### Development dependencies and tests

Install the complete development environment and run the repository test
wrapper:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_tests.py
```

Use `.venv\Scripts\python.exe` on Windows. The wrapper establishes the
repository's headless defaults and returns a non-zero status on failure. Exact
lint and type-check commands are defined in the
[Tests workflow](../.github/workflows/tests.yml).

## Development artifacts

Untagged `main` builds can appear as expiring GitHub Actions artifacts in the
[Windows build workflow](https://github.com/superuser-d0/archlence/actions/workflows/build-windows.yml)
and [Linux build workflow](https://github.com/superuser-d0/archlence/actions/workflows/build-linux.yml).
They require GitHub access, expire according to artifact retention settings,
and are development outputs rather than public releases.

## Troubleshooting

### The clone destination already exists

Do not clone a second copy over the first one. Enter the existing checkout,
inspect it, and update only when it is clean:

```bash
cd ~/archlence
git status
git pull --ff-only
```

### Fish reports an activation syntax error

Use `source .venv/bin/activate.fish`, or skip activation and invoke
`.venv/bin/python` directly.

### PowerShell blocks `Activate.ps1`

Activation is not required. Use `.venv\Scripts\python.exe` directly.

### The AppImage reports a FUSE error

Install the FUSE 2 compatibility package for the distribution, or use
`--appimage-extract-and-run` as shown above.

### An unsigned Windows package triggers SmartScreen

Confirm that the file came from the project's release page and that its SHA-256
matches `SHA256SUMS.txt`. Do not bypass SmartScreen for a mismatched or
unverified file.

## Data retention and recovery

Installing, upgrading, or removing a package does not intentionally delete the
user database. That behavior is not a substitute for recovery planning. A raw
database copy without its matching key material is insufficient.

Before an upgrade, create a verified application backup and retain its recovery
password separately. See [Backup and recovery](BACKUP_RECOVERY.md) and
[Key management](KEY_MANAGEMENT.md).
