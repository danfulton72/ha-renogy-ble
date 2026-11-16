"""Tests for synchronizing manifest requirements from pyproject.toml."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "sync_manifest_requirements.py"


def _load_script() -> Any:
    """Load the sync script as a module."""
    spec = importlib.util.spec_from_file_location("sync_manifest", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_project(tmp_path: Path, library_pin: str) -> tuple[Path, Path]:
    """Write a minimal pyproject.toml and manifest.json pair."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        'name = "example"\n'
        f'dependencies = ["{library_pin}", "homeassistant>=2026.3.0"]\n',
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "domain": "renogy_ble",
                "requirements": ["renogy-ble==2.6.0"],
                "version": "0.9.25",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return pyproject, manifest


def test_sync_copies_library_pin_into_manifest(tmp_path: Path) -> None:
    """A Dependabot pyproject bump is carried into the manifest."""
    script = _load_script()
    pyproject, manifest = _write_project(tmp_path, "renogy-ble==2.13.0")

    assert script.sync(pyproject, manifest, check=False) is False

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["requirements"] == ["renogy-ble==2.13.0"]
    assert data["version"] == "0.9.25"
    assert script.sync(pyproject, manifest, check=False) is True


def test_sync_check_mode_does_not_write(tmp_path: Path) -> None:
    """Check mode reports drift without changing the manifest."""
    script = _load_script()
    pyproject, manifest = _write_project(tmp_path, "renogy-ble==2.13.0")
    before = manifest.read_text(encoding="utf-8")

    assert script.sync(pyproject, manifest, check=True) is False
    assert manifest.read_text(encoding="utf-8") == before


def test_sync_ignores_dependencies_missing_from_manifest() -> None:
    """Project-only dependencies never become Home Assistant requirements."""
    script = _load_script()

    assert script.synchronized_requirements(
        ["renogy_ble==2.6.0"], ["Renogy-BLE==2.12.2", "homeassistant>=2026.3.0"]
    ) == ["Renogy-BLE==2.12.2"]


def test_repository_manifest_lists_the_library() -> None:
    """The manifest must keep a renogy-ble requirement for the sync to update."""
    script = _load_script()
    manifest = json.loads(script.MANIFEST_PATH.read_text(encoding="utf-8"))

    assert any(
        script._normalized_name(requirement) == "renogy-ble"
        for requirement in manifest["requirements"]
    )
