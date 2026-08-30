# Renogy BLE Integration for Home Assistant

[![Tests](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/test.yml/badge.svg)](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/test.yml)
[![Hassfest](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/hassfest.yml/badge.svg)](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/hassfest.yml)
[![HACS](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/validate.yml/badge.svg)](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/validate.yml)
[![Release](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/release.yml/badge.svg)](https://github.com/danfulton72/ha-renogy-ble/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/danfulton72/ha-renogy-ble)](https://github.com/danfulton72/ha-renogy-ble/releases/latest)

**Renogy BLE** is a custom Home Assistant integration for monitoring and controlling supported Renogy devices over Bluetooth Low Energy (BLE). Its Home Assistant domain is `renogy_ble` and HACS installs it into `custom_components/renogy_ble`.

Charge controllers and DCC chargers use BT-1 or BT-2 modules. Supported batteries, inverters, and Smart Shunt 300 devices advertise directly over BLE.

> **Disclaimer:** This integration is experimental software. Use caution when controlling electrical loads, and ensure any connected equipment is properly rated and protected.

## Supported Devices

Supported device families:

- Renogy charge controllers using BT-1 or BT-2, including Rover and Wanderer
- Renogy DC-DC chargers using BT-1 or BT-2, including DCC and RBC model families
- Renogy batteries using the legacy, Battery Pro, or RNGPRO protocol:
  - Legacy `BT-TH-*` names containing `BATT` or `BATTERY`
  - Battery Pro names beginning with `RNGRBP` or `RNGC`
  - RNGPRO-family names beginning with `RNGPRO`
  - Battery Pro advertisements containing manufacturer ID `0xE14C`
- Renogy inverters advertising `RNGRIU*`
- Renogy Smart Shunt 300 devices advertising `RTMShunt300*`

Expected to work, but not yet confirmed:

- Renogy Adventurer

Support is protocol-family based, so behavior can vary by model and firmware. When reporting a problem, include the exact model, Bluetooth name, integration debug logs, and a comparison with the Renogy app.

## Features

- Automatic discovery of supported Renogy BLE devices
- Battery, controller, charger, inverter, and Smart Shunt telemetry
- Energy dashboard compatible sensors where applicable
- DC load control on supported controllers
- Supported DCC charger configuration
- Configurable polling and connection modes
- Automatic error recovery

## Prerequisites

- Home Assistant 2026.3 or newer
- A compatible Bluetooth adapter or Bluetooth proxy
- Bluetooth discovery enabled in Home Assistant

## Installation with HACS

Until this repository is included in the HACS default catalog, add it as a custom repository:

1. Open HACS in Home Assistant.
2. Open the HACS menu and choose **Custom repositories**.
3. Add `https://github.com/danfulton72/ha-renogy-ble` with category **Integration**.
4. Search for **Renogy BLE** and install it.
5. Restart Home Assistant.
6. Go to **Settings > Devices & services > Add Integration**, search for **Renogy BLE**, and complete setup.

HACS installs the integration as `custom_components/renogy_ble`.

## Manual Installation

Copy `custom_components/renogy_ble` from this repository into your Home Assistant configuration directory as `custom_components/renogy_ble`, restart Home Assistant, then add **Renogy BLE** from **Settings > Devices & services**.

## Configuration

The integration is configured through the Home Assistant UI. Device options include polling interval and, for supported devices, connection mode.

- **Polling Interval:** 10–600 seconds, default 60 seconds.
- **Connection Mode:** Smart Shunt 300 supports `sustained` and `intermittent`; batteries, controllers, DCC chargers, and inverters support `intermittent` and `persistent_session`.
- See [Connection modes](docs/connection-modes.md) for details.

## Sensors and Controls

Depending on the device, Renogy BLE exposes battery voltage/current/power/temperature/state of charge, solar PV metrics, load telemetry, inverter AC metrics, controller information, Smart Shunt metrics, energy statistics, DC load switching, and supported DCC configuration entities.

> **Caution:** Write operations can change charger or load behavior. Verify values and electrical protection before relying on control features.

## Troubleshooting

### Enable Debug Logging

1. Open the [Renogy BLE integration](https://my.home-assistant.io/redirect/integration/?domain=renogy_ble).
2. Select **Enable debug logging**.
3. Reproduce the issue.
4. Download or copy the relevant Home Assistant logs.

### Device Not Found

- Verify the device family is supported.
- Confirm BT-1/BT-2 hardware where required.
- Confirm Bluetooth is enabled and the device is in range.
- For batteries/inverters/shunts, verify the advertised Bluetooth name matches the documented patterns.
- Restart the Bluetooth adapter or proxy if discovery has stalled.

## Releases and Versioning

GitHub releases are the authoritative version source for this repository. Every non-release commit pushed to `main` is released automatically using the next patch SemVer tag (`vX.Y.Z`). Before the tag and GitHub release are created, the release workflow synchronizes that version into `custom_components/renogy_ble/manifest.json` and commits the version update to `main`.

The initial detached repository starts at `v0.9.0`; subsequent `main` commits advance the patch version automatically. HACS therefore sees the same version in the GitHub release and Home Assistant manifest.

## Development

This repository uses `uv`, pytest, Ruff, and `ty`.

```bash
uv sync --all-groups
uv run ruff format .
uv run ruff check . --output-format=github
uv run ty check . --output-format=github
uv run pytest tests
```

Pull requests and pushes are validated with HACS and Home Assistant Hassfest.

## Support

Report bugs and feature requests at [GitHub Issues](https://github.com/danfulton72/ha-renogy-ble/issues). Include your Home Assistant version, Renogy BLE version, exact device model/Bluetooth name, and relevant debug logs.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
