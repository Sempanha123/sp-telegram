from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    expected = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    print(f"Python executable: {sys.executable}")
    print(f"Expected project venv: {expected}")
    print(f"Using project venv: {Path(sys.executable).resolve() == expected.resolve()}")
    print(f"Python version: {sys.version.split()[0]}")
    for name in ("PySide6", "telethon", "qrcode", "keyring"):
        try:
            mod = importlib.import_module(name)
            print(f"{name}: {getattr(mod, '__version__', 'imported')}")
        except Exception as exc:
            print(f"{name}: unavailable ({exc})")
    result = subprocess.run([sys.executable, "-m", "pip", "check"], check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
