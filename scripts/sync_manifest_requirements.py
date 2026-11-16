"""Copy runtime dependency pins from pyproject.toml into manifest.json.

Home Assistant installs the requirements listed in the integration manifest,
while Dependabot only updates pyproject.toml and uv.lock. The release
workflows run this script so every published release ships the library
version that CI tested. Only packages already listed in the manifest are
synchronized, so development-only dependencies never reach Home Assistant.

Usage: python scripts/sync_manifest_requirements.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT / "pyproject.toml"
MANIFEST_PATH = ROOT / "custom_components" / "renogy_ble" / "manifest.json"

# A requirement name ends at the first version operator, extra or marker.
_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalized_name(requirement: str) -> str:
    """Return the PEP 503 normalized package name of a requirement string."""
    match = _NAME_PATTERN.match(requirement)
    if match is None:
        raise ValueError(f"Cannot parse requirement: {requirement!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def synchronized_requirements(
    manifest_requirements: list[str], project_dependencies: list[str]
) -> list[str]:
    """Return manifest requirements with pins taken from the project."""
    project_pins = {_normalized_name(dep): dep for dep in project_dependencies}
    return [
        project_pins.get(_normalized_name(requirement), requirement)
        for requirement in manifest_requirements
    ]


def sync(pyproject_path: Path, manifest_path: Path, *, check: bool) -> bool:
    """Synchronize the manifest and return True when it was already in sync."""
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    current = list(manifest.get("requirements", []))
    updated = synchronized_requirements(
        current, list(pyproject["project"]["dependencies"])
    )
    if updated == current:
        return True

    if not check:
        manifest["requirements"] = updated
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    for old, new in zip(current, updated, strict=True):
        if old != new:
            print(f"{manifest_path.name}: {old} -> {new}")
    return False


def main() -> int:
    """Run the synchronization from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report differences and exit non-zero without writing",
    )
    args = parser.parse_args()
    in_sync = sync(PYPROJECT_PATH, MANIFEST_PATH, check=args.check)
    return 0 if in_sync or not args.check else 1


if __name__ == "__main__":
    sys.exit(main())
