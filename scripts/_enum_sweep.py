"""One-shot PySide6 enum-shortcut canonicalization sweep.

PySide6 6.11 stubs declare enums as nested classes (e.g. ``Qt.AlignmentFlag``,
``QAbstractItemView.SelectionBehavior``) and do NOT declare the runtime shortcut
attributes (``Qt.AlignmentFlag.AlignCenter``, ``QAbstractItemView.SelectionBehavior.SelectRows``).  Pylance
therefore flags every shortcut usage.  This script rewrites shortcuts to their
canonical nested-enum forms, which are runtime-equal.

The mappings are derived by parsing the installed PySide6 stubs
(``QtCore.pyi``, ``QtWidgets.pyi``, ``QtGui.pyi``) so they stay in sync with the
installed PySide6 version.  Every top-level class with nested enum classes is
covered (``Qt``, ``QPainter``, ``QStyle``, ``QEvent``, ``QAbstractItemView``,
``QHeaderView``, ``QMessageBox``, ...).  Explicit overrides resolve ambiguous
member names.

Usage:  python scripts/_enum_sweep.py [--dry-run]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"c:/Users/Rg Gear/Desktop/sp_telegram")
VENV = ROOT / ".venv" / "Lib" / "site-packages" / "PySide6"
STUBS = [VENV / "QtCore.pyi", VENV / "QtWidgets.pyi", VENV / "QtGui.pyi"]
TARGETS = [ROOT / "app", ROOT / "main.py", ROOT / "scripts"]

# Explicit, runtime-verified canonical mappings for non-Qt classes.
EXTRA: dict[str, dict[str, str]] = {
    "QAbstractItemView": {
        # ScrollMode
        "ScrollPerItem": "ScrollMode.ScrollPerItem",
        "ScrollPerPixel": "ScrollMode.ScrollPerPixel",
        # SelectionBehavior
        "SelectItems": "SelectionBehavior.SelectItems",
        "SelectRows": "SelectionBehavior.SelectRows",
        "SelectColumns": "SelectionBehavior.SelectColumns",
        # SelectionMode
        "NoSelection": "SelectionMode.NoSelection",
        "SingleSelection": "SelectionMode.SingleSelection",
        "MultiSelection": "SelectionMode.MultiSelection",
        "ExtendedSelection": "SelectionMode.ExtendedSelection",
        "ContiguousSelection": "SelectionMode.ContiguousSelection",
        # EditTrigger
        "NoEditTriggers": "EditTrigger.NoEditTriggers",
        "CurrentChanged": "EditTrigger.CurrentChanged",
        "DoubleClicked": "EditTrigger.DoubleClicked",
        "SelectedClicked": "EditTrigger.SelectedClicked",
        "EditKeyPressed": "EditTrigger.EditKeyPressed",
        "AnyKeyPressed": "EditTrigger.AnyKeyPressed",
        "AllEditTriggers": "EditTrigger.AllEditTriggers",
    },
    "QHeaderView": {
        # ResizeMode
        "Interactive": "ResizeMode.Interactive",
        "Fixed": "ResizeMode.Fixed",
        "Stretch": "ResizeMode.Stretch",
        "ResizeToContents": "ResizeMode.ResizeToContents",
        "Custom": "ResizeMode.Custom",
    },
    "QMessageBox": {
        # ButtonRole
        "AcceptRole": "ButtonRole.AcceptRole",
        "RejectRole": "ButtonRole.RejectRole",
        "ActionRole": "ButtonRole.ActionRole",
        "DestructiveRole": "ButtonRole.DestructiveRole",
        "HelpRole": "ButtonRole.HelpRole",
        "YesRole": "ButtonRole.YesRole",
        "NoRole": "ButtonRole.NoRole",
        "ApplyRole": "ButtonRole.ApplyRole",
        "ResetRole": "ButtonRole.ResetRole",
        # Icon
        "Information": "Icon.Information",
        "Warning": "Icon.Warning",
        "Critical": "Icon.Critical",
        "Question": "Icon.Question",
        # StandardButton (safety net; already canonicalized)
        "Yes": "StandardButton.Yes",
        "No": "StandardButton.No",
        "Cancel": "StandardButton.Cancel",
        "Ok": "StandardButton.Ok",
        "Open": "StandardButton.Open",
        "Save": "StandardButton.Save",
        "Close": "StandardButton.Close",
        "Abort": "StandardButton.Abort",
        "Retry": "StandardButton.Retry",
        "Ignore": "StandardButton.Ignore",
        "YesToAll": "StandardButton.YesToAll",
        "NoToAll": "StandardButton.NoToAll",
        "RestoreDefaults": "StandardButton.RestoreDefaults",
        "Help": "StandardButton.Help",
        "Reset": "StandardButton.Reset",
        "Apply": "StandardButton.Apply",
        "Discard": "StandardButton.Discard",
    },
}


def parse_stub_mappings() -> dict[str, dict[str, str]]:
    """Parse every top-level class with nested enums from the PySide6 stubs.

    Returns ``{Class: {member: Enum.member}}``.  Ambiguous member names (the
    same name in multiple enums of one class) keep the first mapping and are
    reported as warnings.
    """
    result: dict[str, dict[str, str]] = {}
    collisions: dict[str, dict[str, list[str]]] = {}
    for stub in STUBS:
        text = stub.read_text(encoding="utf-8")
        current_class: str | None = None
        current_enum: str | None = None
        for line in text.splitlines():
            m = re.match(r"^class (\w+)\(", line)
            if m:
                current_class = m.group(1)
                current_enum = None
                result.setdefault(current_class, {})
                continue
            if current_class is None:
                continue
            m = re.match(r"^    class (\w+)\(enum\.(?:Enum|IntEnum|IntFlag|Flag)\):", line)
            if m:
                current_enum = m.group(1)
                continue
            if line.startswith("    class "):
                current_enum = None  # nested non-enum class
                continue
            if current_enum:
                m = re.match(r"^        (\w+)\s*=", line)
                if m:
                    member = m.group(1)
                    canonical = f"{current_enum}.{member}"
                    cls_map = result[current_class]
                    if member in cls_map and cls_map[member] != canonical:
                        collisions.setdefault(current_class, {}).setdefault(
                            member, [cls_map[member]]
                        ).append(canonical)
                    else:
                        cls_map[member] = canonical
    if collisions:
        print("WARNING: ambiguous members (first mapping wins):")
        for cls, members in sorted(collisions.items()):
            for name, forms in sorted(members.items()):
                print(f"  {cls}.{name}: {forms}")
    return result


# Some enum member names are shared by multiple Qt enums.  The stub parser picks
# the first occurrence, which is wrong for these well-known cases.  Override them
# with the canonical enum that matches how the app uses them.
_ITEM_DATA_ROLES = [
    "DisplayRole", "DecorationRole", "EditRole", "ToolTipRole", "StatusTipRole",
    "WhatsThisRole", "SizeHintRole", "FontRole", "TextAlignmentRole",
    "BackgroundRole", "ForegroundRole", "CheckStateRole", "AccessibleTextRole",
    "AccessibleDescriptionRole", "InitialSortOrderRole", "UserRole",
]
_KEYS = [
    "Key_Escape", "Key_Tab", "Key_Backtab", "Key_Backspace", "Key_Return",
    "Key_Enter", "Key_Insert", "Key_Delete", "Key_Pause", "Key_Print",
    "Key_SysReq", "Key_Clear", "Key_Home", "Key_End", "Key_Left", "Key_Up",
    "Key_Right", "Key_Down", "Key_PageUp", "Key_PageDown", "Key_Shift",
    "Key_Control", "Key_Meta", "Key_Alt", "Key_AltGr", "Key_CapsLock",
    "Key_NumLock", "Key_ScrollLock", "Key_F1", "Key_F2", "Key_F3", "Key_F4",
    "Key_F5", "Key_F6", "Key_F7", "Key_F8", "Key_F9", "Key_F10", "Key_F11",
    "Key_F12", "Key_F13", "Key_F14", "Key_F15", "Key_F16", "Key_F17",
    "Key_F18", "Key_F19", "Key_F20", "Key_F21", "Key_F22", "Key_F23",
    "Key_F24", "Key_F25", "Key_F26", "Key_F27", "Key_F28", "Key_F29",
    "Key_F30", "Key_F31", "Key_F32", "Key_F33", "Key_F34", "Key_F35",
    "Key_Super_L", "Key_Super_R", "Key_Menu", "Key_Hyper_L", "Key_Hyper_R",
    "Key_Help", "Key_Direction_L", "Key_Direction_R", "Key_Space", "Key_Any",
    "Key_Exclam", "Key_QuoteDbl", "Key_NumberSign", "Key_Dollar", "Key_Percent",
    "Key_Ampersand", "Key_Apostrophe", "Key_ParenLeft", "Key_ParenRight",
    "Key_Asterisk", "Key_Plus", "Key_Comma", "Key_Minus", "Key_Period",
    "Key_Slash", "Key_0", "Key_1", "Key_2", "Key_3", "Key_4", "Key_5",
    "Key_6", "Key_7", "Key_8", "Key_9", "Key_Colon", "Key_Semicolon",
    "Key_Less", "Key_Equal", "Key_Greater", "Key_Question", "Key_At",
    "Key_A", "Key_B", "Key_C", "Key_D", "Key_E", "Key_F", "Key_G", "Key_H",
    "Key_I", "Key_J", "Key_K", "Key_L", "Key_M", "Key_N", "Key_O", "Key_P",
    "Key_Q", "Key_R", "Key_S", "Key_T", "Key_U", "Key_V", "Key_W", "Key_X",
    "Key_Y", "Key_Z", "Key_BracketLeft", "Key_Backslash", "Key_BracketRight",
    "Key_AsciiCircum", "Key_Underscore", "Key_QuoteLeft", "Key_BraceLeft",
    "Key_Bar", "Key_BraceRight", "Key_AsciiTilde", "Key_nobreakspace",
    "Key_exclamdown", "Key_cent", "Key_sterling", "Key_currency", "Key_yen",
    "Key_brokenbar", "Key_section", "Key_diaeresis", "Key_copyright",
    "Key_ordfeminine", "Key_guillemotleft", "Key_notsign", "Key_hyphen",
    "Key_registered", "Key_macron", "Key_degree", "Key_plusminus",
    "Key_twosuperior", "Key_threesuperior", "Key_acute", "Key_mu",
    "Key_paragraph", "Key_periodcentered", "Key_cedilla", "Key_onesuperior",
    "Key_masculine", "Key_guillemotright", "Key_onequarter", "Key_onehalf",
    "Key_threequarters", "Key_questiondown", "Key_Agrave", "Key_Aacute",
    "Key_Acircumflex", "Key_Atilde", "Key_Adiaeresis", "Key_Aring",
    "Key_AE", "Key_Ccedilla", "Key_Egrave", "Key_Eacute", "Key_Ecircumflex",
    "Key_Ediaeresis", "Key_Igrave", "Key_Iacute", "Key_Icircumflex",
    "Key_Idiaeresis", "Key_ETH", "Key_Ntilde", "Key_Ograve", "Key_Oacute",
    "Key_Ocircumflex", "Key_Otilde", "Key_Odiaeresis", "Key_multiply",
    "Key_Ooblique", "Key_Ugrave", "Key_Uacute", "Key_Ucircumflex",
    "Key_Udiaeresis", "Key_Yacute", "Key_THORN", "Key_ssharp", "Key_division",
    "Key_ydiaeresis", "Key_Multiplication", "Key_Addition", "Key_Subtraction",
    "Key_Select", "Key_Execute", "Key_Printer", "Key_Play", "Key_Zoom",
    "Key_Cancel", "Key_Context1", "Key_Context2", "Key_Context3",
    "Key_Context4", "Key_Call", "Key_Hangup", "Key_Flip", "Key_No",
    "Key_ClearSelection", "Key_ScrollUp", "Key_ScrollDown", "Key_Red",
    "Key_Green", "Key_Yellow", "Key_Blue", "Key_ChannelUp", "Key_ChannelDown",
    "Key_MediaLast", "Key_MediaPause", "Key_MediaPlay", "Key_MediaTogglePause",
    "Key_MediaRecord", "Key_MediaFastForward", "Key_MediaRewind",
    "Key_MediaNext", "Key_MediaPrev", "Key_MediaStop", "Key_MediaPlayPause",
    "Key_Back", "Key_Forward", "Key_Refresh", "Key_Stop", "Key_Search",
    "Key_Favorites", "Key_HomePage", "Key_VolumeMute", "Key_VolumeDown",
    "Key_VolumeUp", "Key_Unknown", "Key_AltGr", "Key_Launch0", "Key_Launch1",
    "Key_Launch2", "Key_Launch3", "Key_Launch4", "Key_Launch5", "Key_Launch6",
    "Key_Launch7", "Key_Launch8", "Key_Launch9", "Key_LaunchA", "Key_LaunchB",
    "Key_LaunchC", "Key_LaunchD", "Key_LaunchE", "Key_LaunchF",
    "Key_LaunchG", "Key_LaunchH", "Key_MonBrightnessUp", "Key_MonBrightnessDown",
    "Key_KeyboardLightOnOff", "Key_KeyboardBrightnessUp",
    "Key_KeyboardBrightnessDown", "Key_PowerDown", "Key_Sleep", "Key_WakeUp",
    "Key_Standby", "Key_MediaLast", "Key_MediaPause", "Key_MediaPlay",
    "Key_MediaTogglePause", "Key_MediaRecord", "Key_MediaFastForward",
    "Key_MediaRewind", "Key_MediaNext", "Key_MediaPrev", "Key_MediaStop",
    "Key_MediaPlayPause", "Key_Back", "Key_Forward", "Key_Refresh", "Key_Stop",
    "Key_Search", "Key_Favorites", "Key_HomePage", "Key_VolumeMute",
    "Key_VolumeDown", "Key_VolumeUp", "Key_Unknown", "Key_AltGr",
    "Key_Launch0", "Key_Launch1", "Key_Launch2", "Key_Launch3", "Key_Launch4",
    "Key_Launch5", "Key_Launch6", "Key_Launch7", "Key_Launch8", "Key_Launch9",
    "Key_LaunchA", "Key_LaunchB", "Key_LaunchC", "Key_LaunchD", "Key_LaunchE",
    "Key_LaunchF", "Key_LaunchG", "Key_LaunchH", "Key_MonBrightnessUp",
    "Key_MonBrightnessDown", "Key_KeyboardLightOnOff",
    "Key_KeyboardBrightnessUp", "Key_KeyboardBrightnessDown", "Key_PowerDown",
    "Key_Sleep", "Key_WakeUp", "Key_Standby", "Key_MediaLast",
    "Key_MediaPause", "Key_MediaPlay", "Key_MediaTogglePause",
    "Key_MediaRecord", "Key_MediaFastForward", "Key_MediaRewind",
    "Key_MediaNext", "Key_MediaPrev", "Key_MediaStop", "Key_MediaPlayPause",
    "Key_Back", "Key_Forward", "Key_Refresh", "Key_Stop", "Key_Search",
    "Key_Favorites", "Key_HomePage", "Key_VolumeMute", "Key_VolumeDown",
    "Key_VolumeUp", "Key_Unknown", "Key_AltGr",
]

_QT_OVERRIDES: dict[str, str] = {}
for _role in _ITEM_DATA_ROLES:
    _QT_OVERRIDES[_role] = f"ItemDataRole.{_role}"
for _key in _KEYS:
    _QT_OVERRIDES[_key] = f"Key.{_key}"


def build_regex(class_name: str, members: dict[str, str]) -> re.Pattern:
    names = sorted(members.keys(), key=len, reverse=True)
    return re.compile(
        r"(?<![\w.])" + re.escape(class_name) + r"\.("
        + "|".join(re.escape(n) for n in names) + r")\b"
    )


def sweep_file(path: Path, regexes: list[tuple[str, re.Pattern, dict[str, str]]],
               dry_run: bool) -> list[str]:
    text = path.read_text(encoding="utf-8")
    changes: list[str] = []

    def make_repl(class_name: str, mapping: dict[str, str]):
        def repl(m: re.Match) -> str:
            member = m.group(1)
            changes.append(f"  {m.group(0)} -> {class_name}.{mapping[member]}")
            return f"{class_name}.{mapping[member]}"
        return repl

    new_text = text
    for class_name, regex, mapping in regexes:
        new_text = regex.sub(make_repl(class_name, mapping), new_text)
    if new_text != text:
        if not dry_run:
            path.write_text(new_text, encoding="utf-8")
        return changes
    return []


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    mappings = parse_stub_mappings()
    # Resolve known ambiguous Qt members (ItemDataRole / Key collisions).
    mappings.setdefault("Qt", {}).update(_QT_OVERRIDES)
    # Explicit verified mappings win over the stub parser.
    for class_name, mapping in EXTRA.items():
        mappings.setdefault(class_name, {}).update(mapping)
    total_members = sum(len(m) for m in mappings.values())
    print(f"Parsed {total_members} enum members across {len(mappings)} classes from stubs.")
    regexes: list[tuple[str, re.Pattern, dict[str, str]]] = [
        (class_name, build_regex(class_name, mapping), mapping)
        for class_name, mapping in mappings.items()
        if mapping
    ]

    total = 0
    files_changed = 0
    for target in TARGETS:
        if target.is_file():
            paths = [target]
        else:
            paths = sorted(target.rglob("*.py"))
        for path in paths:
            changes = sweep_file(path, regexes, dry_run)
            if changes:
                files_changed += 1
                total += len(changes)
                print(f"{path.relative_to(ROOT)} ({len(changes)}):")
                for c in changes:
                    print(c)
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Total: {total} replacements in {files_changed} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())