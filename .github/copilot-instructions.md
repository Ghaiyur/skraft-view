# SKRAFT View Copilot Instructions

## Project overview

SKRAFT View is a Django-based local system monitor intended to feel like a lightweight desktop app.

The app currently:

- serves a local dashboard
- opens in the user's default browser
- monitors the current machine only
- aims to package into standalone desktop builds

## Main project structure

- `launch_skraft_view.py` - local launcher and runtime bootstrap
- `dashboard/` - metrics collection, runtime control, views, and tests
- `skraft_view/` - Django settings and URL configuration
- `templates/` - dashboard HTML
- `static/` - CSS, JavaScript, and image assets
- `.github/workflows/` - CI and release automation

## Development conventions

- Prefer small, direct changes that preserve the current local-first behavior.
- Do not introduce cloud features, telemetry, or remote sync unless explicitly requested.
- Keep the app lightweight and easy to package.
- Preserve the existing dashboard style and project naming.
- Prefer ASCII unless a file already needs other characters.
- Avoid adding unnecessary dependencies.

## Python and Django expectations

- Use Python 3.12.
- Install dependencies from `requirements.txt`.
- Use `python manage.py check` for framework validation.
- Use `python manage.py test` for tests.
- Keep Django settings compatible with local desktop-style use.

## Lint and formatting

Before proposing final changes, prefer to validate with:

- `ruff format dashboard skraft_view launch_skraft_view.py manage.py`
- `ruff check dashboard skraft_view launch_skraft_view.py manage.py`

## Packaging expectations

- Windows packaging currently centers on `build_standalone.ps1`.
- Do not assume end users have Python or Django installed.
- Prefer changes that keep standalone packaging straightforward.

## When making changes

- Update docs when developer workflow changes.
- Keep README instructions practical and simple.
- If changing CI, keep checks fast and easy to understand.
