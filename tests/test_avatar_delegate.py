from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel

from app.models.base_table_model import BaseTableModel
from app.widgets.avatar_delegate import AvatarDelegate


def test_avatar_delegate_reads_subtitle_through_proxy_model(qapp) -> None:
    source = BaseTableModel(
        [{"_id": 7, "Account": "Sem Panha", "Username": "@sem_panaha"}],
        ["Account", "Username"],
    )
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(source)
    delegate = AvatarDelegate(
        None,
        "account",
        "_id",
        "Account",
        account_id_attr="_id",
        subtitle_column="Username",
    )

    assert delegate._entity_id(proxy.index(0, 0)) == 7
    assert delegate._entity_name(proxy.index(0, 0)) == "Sem Panha"
    assert delegate._entity_account_id(proxy.index(0, 0)) == 7
    assert delegate._subtitle(proxy.index(0, 0)) == "@sem_panaha"


def test_avatar_delegate_ignores_empty_subtitles(qapp) -> None:
    model = BaseTableModel(
        [{"_id": 9, "Group": "Private Group", "Username": "—"}],
        ["Group", "Username"],
    )
    delegate = AvatarDelegate(
        None, "group", "_id", "Group", subtitle_column="Username"
    )

    assert delegate._subtitle(model.index(0, 0)) == ""
