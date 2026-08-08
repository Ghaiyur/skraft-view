# skraft-view

[![License](https://img.shields.io/github/license/Ghaiyur/skraft-view?label=license)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/Ghaiyur/skraft-view?display_name=tag&label=release)](https://github.com/Ghaiyur/skraft-view/releases)
[![Last Commit](https://img.shields.io/github/last-commit/Ghaiyur/skraft-view?label=last%20commit)](https://github.com/Ghaiyur/skraft-view/commits/master)
[![Basic Checks](https://github.com/Ghaiyur/skraft-view/actions/workflows/checks.yml/badge.svg)](https://github.com/Ghaiyur/skraft-view/actions/workflows/checks.yml)
[![Windows Release Build](https://github.com/Ghaiyur/skraft-view/actions/workflows/release-windows.yml/badge.svg)](https://github.com/Ghaiyur/skraft-view/actions/workflows/release-windows.yml)

SKRAFT View is an open source desktop system monitor with a local web dashboard.

It is being built to feel simple for end users:

- download it
- double-click it
- let it open in the default browser
- see live machine information without a cloud account

## What it does

The current app focuses on lightweight local visibility for the computer it is running on.

Right now that includes:

- live CPU, memory, disk, and network metrics
- a `What's on it` tab for hardware and OS details
- light and dark themes
- local-first behavior with no cloud account requirement

## Project goal

The goal for `skraft view` is a cross-platform monitor that can eventually ship as:

- Windows: `SKRAFT View.exe`
- macOS: `SKRAFT View.app`
- Linux: `SKRAFT View.AppImage` or another native package

End users should not need to install:

- Python
- Django
- a virtual environment

## Run from source

For development, the single launcher is:

```bash
python launch_skraft_view.py
```

That launcher is intended to handle local startup behavior across operating systems.

## Development setup

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python launch_skraft_view.py
```

## Windows packaging

The current standalone Windows build script is:

```powershell
.\build_standalone.ps1
```

It builds a self-contained Windows app that bundles:

- Python
- Django
- `psutil`
- templates
- static assets

The build output is written to:

```text
build\windows\SKRAFT View\
```

## GitHub releases

The repository includes a Windows release workflow:

```text
.github/workflows/release-windows.yml
```

Typical release flow:

- create or push a tag like `v0.1.0`
- let GitHub Actions build the Windows package
- publish the generated build in the repository Releases section

## Project structure

- `launch_skraft_view.py` - local launcher
- `build_standalone.ps1` - Windows packaging script
- `dashboard/` - metrics collection, views, and runtime control
- `skraft_view/` - Django project configuration
- `templates/` - dashboard templates
- `static/` - CSS, JavaScript, and image assets

## Notes

- `psutil` is used for lightweight cross-platform metrics.
- The Terms section in the app is still starter content and will evolve over time.
