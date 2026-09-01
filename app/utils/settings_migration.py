from __future__ import annotations

from PySide6.QtCore import QSettings

# Compatibility-only namespaces from releases before the SP Telegram rename.
# These strings are never shown in the UI and can be removed in a future major
# version after users have migrated their local UI settings.
LEGACY_QSETTINGS_NAMESPACES = (
    ("TG Control Center", "TG Control Center Premium"),
)

FULL_USERNAME_MIGRATION_KEY = "ui/migrations/full_usernames_v1"
MASK_USERNAME_KEY = "ui/table_display/mask_usernames"

# The soft-light theme is the product default from this release on.  Profiles
# created before the redesign kept ``ui/theme=dark`` in QSettings, and because
# MainWindow._restore_state() re-applies the stored value at startup it silently
# overrode the new default, so the redesign was never visible on upgrade.
LIGHT_THEME_MIGRATION_KEY = "ui/migrations/soft_light_default_v1"
THEME_KEY = "ui/theme"
DEFAULT_THEME = "light"


def migrate_legacy_qsettings() -> int:
    """Copy legacy UI-state keys into the current QSettings namespace once.

    Business data remains in SQLite; this only preserves window geometry, last
    page, table widths, theme/language UI state and similar preferences.
    Existing current values always win.
    """
    current = QSettings()
    copied = 0
    for organization, application in LEGACY_QSETTINGS_NAMESPACES:
        legacy = QSettings(organization, application)
        for key in legacy.allKeys():
            if current.contains(key):
                continue
            current.setValue(key, legacy.value(key))
            copied += 1
    # The Member Pool now defaults to readable Telegram usernames.  Apply this
    # once for users whose older profile retained username masking; later user
    # changes still win because the migration marker prevents another reset.
    if not current.contains(FULL_USERNAME_MIGRATION_KEY):
        current.setValue(MASK_USERNAME_KEY, False)
        current.setValue(FULL_USERNAME_MIGRATION_KEY, True)
        copied += 1
    # The soft-light theme is now the product default.  Profiles created before
    # the redesign still carry ``ui/theme=dark`` from the old default, which the
    # window restores at startup and which therefore hid the new design
    # entirely.  Move those profiles onto the new default exactly once; any
    # later explicit user choice wins because the marker is never re-applied.
    if not current.contains(LIGHT_THEME_MIGRATION_KEY):
        if str(current.value(THEME_KEY, DEFAULT_THEME)).strip().lower() != "light":
            current.setValue(THEME_KEY, DEFAULT_THEME)
        current.setValue(LIGHT_THEME_MIGRATION_KEY, True)
        copied += 1
    if copied:
        current.sync()
    return copied
