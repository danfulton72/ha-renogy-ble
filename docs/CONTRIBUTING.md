# Contributing to Renogy BLE

Thanks for contributing to the Home Assistant integration.

Start here:

- Read [`AGENTS.md`](../AGENTS.md) for repository-specific guardrails.
- Read [`README.md`](../README.md) for integration capabilities, prerequisites, and user-facing behavior.

## Scope and Boundaries

`ha-renogy-ble` is the Home Assistant integration layer. The Home Assistant domain is `renogy` and should not be renamed.

- Include Home Assistant lifecycle, config flow, coordinator/entity behavior, and platform wiring changes here.
- Keep BLE transport, Modbus command construction, and response parsing logic in the `renogy-ble` Python dependency.
- The Home Assistant integration depends on `renogy-ble`; dependency direction should remain one-way.

If a fix is protocol/parsing/BLE-transport specific, implement it in the `renogy-ble` library and then bump the dependency here as needed.

## Development Setup

This repository uses `uv` for environment and dependency management.

1. Install dependencies: `uv sync --all-groups`
2. Run tests: `uv run pytest tests`

## Quality Gates

Before opening a PR, run:

1. `uv run ruff format .`
2. `uv run ruff check . --output-format=github`
3. `uv run ty check . --output-format=github`
4. `uv run pytest tests`

GitHub Actions also runs HACS validation and Home Assistant Hassfest.

## Pull Requests

- Add or update tests for behavior changes.
- Keep changes focused and clearly scoped.
- Use conventional commit prefixes (`fix:`, `feat:`, `docs:`, etc.).
- Do not manually edit `custom_components/renogy/manifest.json` solely to bump its version; release automation synchronizes it from the GitHub release sequence.

## Reporting Issues

Use https://github.com/danfulton72/ha-renogy-ble/issues and include:

- Home Assistant version
- Renogy BLE integration version
- Device model and BT module (BT-1/BT-2), if applicable
- Relevant Home Assistant debug logs
- Clear reproduction steps
