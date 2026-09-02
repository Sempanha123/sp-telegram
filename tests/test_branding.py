from __future__ import annotations


def test_brand_assets_load_for_window_and_sidebar(qapp) -> None:
    from app.branding import (
        BRAND_LOGO_PATH,
        BRAND_MARK_PATH,
        brand_icon,
        brand_logo_pixmap,
        brand_mark_pixmap,
    )
    from app.widgets.sidebar import Sidebar

    assert BRAND_LOGO_PATH.is_file()
    assert BRAND_MARK_PATH.is_file()
    assert not brand_icon().isNull()
    assert not brand_logo_pixmap().isNull()
    assert not brand_mark_pixmap().isNull()
    assert brand_logo_pixmap().hasAlphaChannel()

    sidebar = Sidebar()
    try:
        assert sidebar.lbl_brand_icon.text() == ""
        assert sidebar.lbl_brand_icon.pixmap() is not None
        assert not sidebar.lbl_brand_icon.pixmap().isNull()
        assert "SP CAMBO" in sidebar.lbl_edition.text()
        sidebar.set_collapsed(True)
        assert sidebar.lbl_brand_icon.width() == 40
        sidebar.set_collapsed(False)
        assert sidebar.lbl_brand_icon.width() == 54
    finally:
        sidebar.deleteLater()
        qapp.processEvents()
