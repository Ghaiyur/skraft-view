# skraft-view

SKRAFT View monitors performance, temperatures, and hardware details in a lightweight local dashboard.

## What it is

`skraft view` is meant to be an open-source system monitor that works across Windows, macOS, and Linux.

The experience we are aiming for is simple:

- download it for your operating system
- double-click it
- let it open automatically in your default browser
- view live system information without needing a cloud account

## How end users should run it

End users should not need to install Python, Django, or a virtual environment.

The intended release format is:

- Windows: `SKRAFT View.exe`
- macOS: `SKRAFT View.app`
- Linux: `SKRAFT View.AppImage` or another packaged binary

Each release should:

- include its own Python runtime
- bundle Django and other dependencies
- launch locally on the machine
- open the default browser automatically
- store app data in the user profile

## One launcher for source builds

For source code runs, the single launcher entry point is:

```bash
python launch_skraft_view.py
```

That file is the one startup path that should handle launch behavior across operating systems.

## Suggested commit title

If you want a single commit title for the work so far, a strong option is:

```text
Build SKRAFT View desktop monitor with standalone Windows packaging
```

## Standalone packaging

The current Windows packaging script is:

```powershell
.\build_standalone.ps1
```

Its job is to build a standalone app that bundles:

- Python
- Django
- `psutil`
- templates
- static assets

The output should be placed in:

```text
build\windows\SKRAFT View\
```

## GitHub Releases

The repository now includes a Windows release workflow:

```text
.github/workflows/release-windows.yml
```

How it works:

- push a tag like `v0.1.0`
- GitHub Actions builds the standalone Windows app
- the workflow zips the packaged build
- the zip is uploaded to the repository's Releases section

This gives end users a simple download from GitHub Releases instead of asking them to build the app locally.

## Development

If you are working on the project itself, use a local virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python launch_skraft_view.py
```

## Current features

- Live CPU, memory, disk, and network monitoring
- A "What's on it" tab for hardware and OS details
- Light and dark themes
- Transparent SKRAFT logo support
- Local-first behavior

## Project structure

- `launch_skraft_view.py` - source launcher
- `build_standalone.ps1` - Windows standalone build script
- `build/` - final packaged builds by operating system
- `dashboard/` - monitoring views and system probes
- `skraft_view/` - Django project settings
- `templates/` - HTML templates
- `static/` - CSS, JavaScript, and logo assets

## Notes

- `psutil` is used for lightweight cross-platform metrics.
- The legal pages are still starter content and should be reviewed before release.
- This project is not affiliated with NZXT.
