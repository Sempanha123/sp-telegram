# Design tokens for SP Telegram

# Colors
BASE_BACKGROUND = "#0B1020"
BASE_SURFACE = "#11182B"
BASE_ELEVATED = "#172036"
BASE_PANEL = "#0E1628"
BASE_CARD = "#141D32"

# Text colors
TEXT_PRIMARY = "#F5F7FF"
TEXT_SECONDARY = "#B7C1D9"
TEXT_MUTED = "#7F8BA6"
TEXT_DISABLED = "#4D5870"

# Accent colors
ACCENT_PRIMARY = "#6D7CFF"
ACCENT_SECONDARY = "#22D3EE"
ACCENT_SUCCESS = "#34D399"
ACCENT_WARNING = "#FBBF24"
ACCENT_DANGER = "#FB7185"
ACCENT_INFO = "#38BDF8"

# Borders
BORDER_PRIMARY = "#2B3855"
BORDER_SECONDARY = "#405171"

# Shadows
SHADOW_SMALL = "0 2px 4px rgba(0, 0, 0, 0.1)"
SHADOW_MEDIUM = "0 4px 6px rgba(0, 0, 0, 0.15)"
SHADOW_LARGE = "0 6px 8px rgba(0, 0, 0, 0.2)"

# Spacing
SPACING_XS = "4px"
SPACING_SM = "8px"
SPACING_MD = "12px"
SPACING_LG = "16px"
SPACING_XL = "24px"

# Border radius
RADIUS_SM = "4px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"
RADIUS_XL = "16px"

# Typography
FONT_FAMILY = "Segoe UI, Noto Sans Khmer, sans-serif"
FONT_SIZE_SM = "11px"
FONT_SIZE_MD = "13px"
FONT_SIZE_LG = "16px"
FONT_SIZE_XL = "20px"
FONT_WEIGHT_REGULAR = "400"
FONT_WEIGHT_MEDIUM = "550"
FONT_WEIGHT_SEMIBOLD = "650"
FONT_WEIGHT_BOLD = "700"

# Sidebar dimensions
SIDEBAR_EXPANDED = 240
SIDEBAR_COLLAPSED = 60

# Light theme colors
LIGHT_BASE_BACKGROUND = "#F5F7FB"
LIGHT_BASE_SURFACE = "#FFFFFF"
LIGHT_BASE_ELEVATED = "#F8FAFD"
LIGHT_BASE_PANEL = "#EEF2F8"
LIGHT_BASE_CARD = "#FFFFFF"

LIGHT_TEXT_PRIMARY = "#172033"
LIGHT_TEXT_SECONDARY = "#56627A"
LIGHT_TEXT_MUTED = "#8491A9"
LIGHT_TEXT_DISABLED = "#C5CDDC"

LIGHT_ACCENT_PRIMARY = "#5B5CE2"
LIGHT_ACCENT_SECONDARY = "#0891B2"
LIGHT_ACCENT_SUCCESS = "#059669"
LIGHT_ACCENT_WARNING = "#D97706"
LIGHT_ACCENT_DANGER = "#E11D48"
LIGHT_ACCENT_INFO = "#0284C7"

LIGHT_BORDER_PRIMARY = "#DDE3EE"
LIGHT_BORDER_SECONDARY = "#C5CDDC"

# Status colors
STATUS_OK = "#34D399"
STATUS_WARNING = "#FBBF24"
STATUS_ERROR = "#FB7185"
STATUS_MUTED = "#7F8BA6"

# Light status colors
LIGHT_STATUS_OK = "#0B9D6C"
LIGHT_STATUS_WARNING = "#B45309"
LIGHT_STATUS_ERROR = "#E11D48"
LIGHT_STATUS_MUTED = "#94A3B8"

# Page layout
PAGE_PADDING = 20
TABLE_HEADER_HEIGHT = 40
TABLE_ROW_HEIGHT = 36

# Status badge palettes: ``(background, foreground)``.  Keys are normalized to
# lowercase by both StatusBadge and ModernTableDelegate.
STATUS_COLORS = {
    **{key: ("#10382F", "#6EE7B7") for key in (
        "ok", "active", "connected", "healthy", "success", "completed", "ready", "enabled", "online",
    )},
    **{key: ("#3B2E12", "#FCD34D") for key in (
        "warning", "pending", "queued", "partial", "connecting", "paused", "trial",
    )},
    **{key: ("#3D1E2A", "#FDA4AF") for key in (
        "error", "failed", "restricted", "expired", "suspended", "invalid", "blocked",
    )},
    **{key: ("#1C263A", "#9AA7C0") for key in (
        "muted", "idle", "disabled", "offline", "unknown", "draft", "no accounts", "configuration required",
    )},
}

LIGHT_STATUS_COLORS = {
    **{key: ("#E7F8F1", "#047857") for key in (
        "ok", "active", "connected", "healthy", "success", "completed", "ready", "enabled", "online",
    )},
    **{key: ("#FFF6E5", "#B45309") for key in (
        "warning", "pending", "queued", "partial", "connecting", "paused", "trial",
    )},
    **{key: ("#FDECEF", "#BE123C") for key in (
        "error", "failed", "restricted", "expired", "suspended", "invalid", "blocked",
    )},
    **{key: ("#EEF2F7", "#64748B") for key in (
        "muted", "idle", "disabled", "offline", "unknown", "draft", "no accounts", "configuration required",
    )},
}
