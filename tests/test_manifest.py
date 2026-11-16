"""Tests for integration manifest consistency."""

from __future__ import annotations

import json
import tomllib
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "custom_components" / "renogy_ble" / "manifest.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def _manifest_library_pin() -> str:
    """Return the renogy-ble requirement Home Assistant installs."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pins = [req for req in manifest["requirements"] if req.startswith("renogy-ble")]
    assert len(pins) == 1
    return pins[0]


def _pyproject_library_pin() -> str:
    """Return the renogy-ble requirement used for development and CI."""
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    pins = [
        req
        for req in pyproject["project"]["dependencies"]
        if req.startswith("renogy-ble")
    ]
    assert len(pins) == 1
    return pins[0]


def test_manifest_and_pyproject_pin_same_library_version() -> None:
    """Home Assistant installs from the manifest, so it must match CI."""
    # Dependabot only updates pyproject.toml and uv.lock. Without this check a
    # bump can pass CI while users keep running the older library version.
    assert _manifest_library_pin() == _pyproject_library_pin()


def test_installed_library_matches_manifest_pin() -> None:
    """The tested library version must be the version users receive."""
    pinned = _manifest_library_pin().split("==", 1)[1]
    assert version("renogy-ble") == pinned
