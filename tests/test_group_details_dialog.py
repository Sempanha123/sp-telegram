"""Regression tests for the group double-click / group-details flow.

Covers the user-verified bug where double-clicking a group in All Groups
surfaced a generic "The operation could not be completed. Technical details
were written to the local log." dialog.

Root cause: ``GroupsPage.open_details()`` (and the source/target group pages)
passed ``avatar_service=`` to ``GroupDetailsDialog``, whose ``__init__`` did
not accept that keyword argument, raising ``TypeError`` inside the Qt event
handler and routing to the global exception boundary.
"""

import pytest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QDialog

from app.dialogs.group_details_dialog import GroupDetailsDialog
from app.models.entities import TelegramGroup
from app.models.pagination import PaginationState
from app.pages.groups_page import GroupsPage


@pytest.fixture(autouse=True)
def cleanup_group_dialogs(qapp):
    """Destroy dialogs after each test so Qt objects do not leak between cases."""
    yield
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, GroupDetailsDialog):
            widget.close()
            widget.deleteLater()
    qapp.processEvents()


def _make_group(**overrides):
    data = dict(
        id=7,
        telegram_group_id=123456789,
        title="Test Group",
        username="test_group",
        group_type="SUPERGROUP",
        access_state="PUBLIC",
        status="READY",
        member_count=42,
        is_source=1,
        is_target=1,
        is_managed=1,
        account_name="Primary",
        last_sync_at="2026-08-17T12:00:00Z",
    )
    data.update(overrides)
    return TelegramGroup(**data)


def _make_controller(group=None, details=None):
    controller = MagicMock()
    controller.pagination = PaginationState()
    controller.details.return_value = details if details is not None else {
        "group": group,
        "accounts": [],
        "logs": [],
    }
    controller.accounts_for_group.return_value = []
    return controller


class TestGroupDetailsDialogConstruction:
    """The dialog must accept the kwargs the pages pass to it."""

    def test_accepts_avatar_service_kwarg(self, qapp):
        """BUG: pages pass avatar_service=; the dialog must accept it."""
        group = _make_group()
        controller = _make_controller(group)
        dialog = GroupDetailsDialog(
            controller, group.id, avatar_service=MagicMock()
        )
        assert dialog.group is not None
        assert dialog.group.title == "Test Group"
        dialog.close()

    def test_accepts_member_controller_kwarg(self, qapp):
        """target_groups_page passes member_controller= as well."""
        group = _make_group()
        controller = _make_controller(group)
        dialog = GroupDetailsDialog(
            controller, group.id,
            member_controller=MagicMock(),
            avatar_service=MagicMock(),
        )
        assert dialog.group is not None
        dialog.close()

    def test_valid_group_opens_without_error(self, qapp):
        """A valid group must open the details dialog without raising."""
        group = _make_group()
        controller = _make_controller(group)
        dialog = GroupDetailsDialog(controller, group.id)
        assert dialog.windowTitle() == "Group Details — Test Group"
        assert dialog.tabs.count() >= 4
        dialog.close()


class TestGroupDetailsMissingGroup:
    """Invalid / deleted group references must be handled gracefully."""

    def test_missing_group_rejects_without_raising(self, qapp):
        """A deleted group must not raise; it should reject the dialog."""
        controller = _make_controller(None)
        dialog = GroupDetailsDialog(controller, 999)
        # Dialog should be rejected (not shown) and not crash.
        assert dialog.result() == QDialog.DialogCode.Rejected
        dialog.close()

    def test_details_exception_rejects_without_raising(self, qapp):
        """A controller.details() failure must not raise an unhandled error."""
        controller = MagicMock()
        controller.details.side_effect = RuntimeError("db locked")
        dialog = GroupDetailsDialog(controller, 7)
        assert dialog.result() == QDialog.DialogCode.Rejected
        dialog.close()


class TestGroupsPageOpenDetails:
    """Double-click path: GroupsPage.open_details() must not raise."""

    def test_open_details_with_selection(self, qapp, monkeypatch):
        group = _make_group()
        controller = _make_controller(group)
        page = GroupsPage(controller, avatar_service=MagicMock())
        # Simulate a selected row in the table.
        page.model.replace_rows([group])
        page.table.selectRow(0)
        # Patch the dialog so open_details() does not block on a modal exec().
        captured = {}
        class FakeDialog:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
            def exec(self):
                return QDialog.DialogCode.Accepted
        monkeypatch.setattr(
            "app.pages.groups_page.GroupDetailsDialog", FakeDialog
        )
        # Must not raise (previously raised TypeError on avatar_service kwarg).
        page.open_details()
        assert captured["args"][1] == group.id
        assert captured["kwargs"].get("avatar_service") is not None
        page.close()

    def test_open_details_without_selection_is_noop(self, qapp):
        controller = _make_controller(_make_group())
        page = GroupsPage(controller, avatar_service=MagicMock())
        page.open_details()  # no selection -> no-op, no crash
        page.close()