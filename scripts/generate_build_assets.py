from __future__ import annotations

import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.constants import APP_NAME, APP_VERSION  # noqa: E402


def _numeric_version(version: str) -> tuple[int, int, int, int]:
    parts = [int(x) for x in re.findall(r"\d+", version)[:4]]
    parts.extend([0] * (4 - len(parts)))
    return tuple(parts[:4])  # type: ignore[return-value]


def generate_icon(output: Path) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to generate the Windows icon. "
            "Install the project requirements first."
        ) from exc

    source = ROOT / "assets" / "branding" / "sp_cambo_mark.png"
    if not source.is_file():
        raise SystemExit(f"Brand mark is missing: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.save(
            output,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )


def generate_version_info(output: Path) -> None:
    version = _numeric_version(APP_VERSION)
    dotted = ".".join(str(x) for x in version)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={version},\n"
        f"    prodvers={version},\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable(\n"
        "        '040904B0',\n"
        "        [\n"
        "          StringStruct('CompanyName', 'SP Cambo'),\n"
        f"          StringStruct('FileDescription', '{APP_NAME} Desktop Automation'),\n"
        f"          StringStruct('FileVersion', '{dotted}'),\n"
        "          StringStruct('InternalName', 'SPTelegram'),\n"
        "          StringStruct('OriginalFilename', 'SP Telegram.exe'),\n"
        f"          StringStruct('ProductName', '{APP_NAME}'),\n"
        f"          StringStruct('ProductVersion', '{APP_VERSION}')\n"
        "        ]\n"
        "      )\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n"
    )
    output.write_text(content, encoding="utf-8")


def main() -> int:
    out = ROOT / ".build_assets"
    icon = out / "sp_telegram.ico"
    version_info = out / "version_info.txt"
    generate_icon(icon)
    generate_version_info(version_info)
    print(f"Generated: {icon}")
    print(f"Generated: {version_info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
