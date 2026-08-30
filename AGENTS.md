# Background

ha-renogy-ble is the Renogy BLE custom integration for Home Assistant, written in Python and distributed through HACS. It connects Home Assistant to supported Renogy devices over Bluetooth Low Energy. The Home Assistant integration domain is `renogy_ble` and the integration is installed at `custom_components/renogy_ble`.

The integration depends on the `renogy-ble` Python library for BLE transport, Modbus command construction, and response parsing. This repository is the Home Assistant glue layer.

# Documentation

- Use Markdown for documentation.
- Place project documentation in the `docs/` directory.

# Code Style

- Add comments when code intent is not obvious.
- Comments should be full sentences and end with a period.
- Prefer maintainable, understandable code over unnecessary complexity.

# Python

- Use `uv` to manage Python and packages.
- Use `uv add <package>` instead of `uv pip install <package>`.

# Testing

- Use pytest for Python tests.
- Format and lint with Ruff.
- Type-check with `ty`.

# Releases

- GitHub releases are the authoritative version source.
- Every non-release commit pushed to `main` is released as the next patch SemVer version.
- CI synchronizes the release version into `custom_components/renogy_ble/manifest.json`.
- Do not manually bump the manifest version as part of normal feature/fix commits.

# Commits

Use conventional commit prefixes such as `fix:`, `feat:`, `build:`, `chore:`, `ci:`, `docs:`, `style:`, `refactor:`, `perf:`, or `test:`.

# Before Checking In Code

1. `uv run ruff format .`
2. `uv run ruff check . --output-format=github`
3. `uv run ty check . --output-format=github`
4. `uv run pytest tests`
5. Repeat until all checks pass on a single run.
