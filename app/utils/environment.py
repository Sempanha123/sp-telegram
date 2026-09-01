from __future__ import annotations

import os
import sys
from pathlib import Path


def is_virtual_environment() -> bool:
    """Return True for source-development venvs; packaged executables are exempt."""
    if getattr(sys, "frozen", False):
        return False
    return bool(getattr(sys, "base_prefix", sys.prefix) != sys.prefix or os.environ.get("VIRTUAL_ENV"))


def runtime_environment_summary() -> dict[str, str | bool]:
    return {
        "python_executable": str(Path(sys.executable)),
        "python_version": sys.version.split()[0],
        "virtual_environment": is_virtual_environment(),
    }
