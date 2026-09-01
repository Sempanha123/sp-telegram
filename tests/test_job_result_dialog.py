"""Regression tests for job-result dialog actions."""

from unittest.mock import patch

from PySide6.QtWidgets import QDialog, QPlainTextEdit

from app.dialogs.job_result_dialog import JobResultDialog
from app.models.entities import Job


def _make_dialog(**overrides) -> JobResultDialog:
    values = {
        "id": 42,
        "job_type": "INVITE_MEMBERS",
        "status": "PARTIAL_SUCCESS",
        "total_items": 4,
        "success_count": 1,
        "failed_count": 1,
        "skipped_count": 1,
        "finished_at": "2026-08-31T12:00:00Z",
    }
    values.update(overrides)
    items = [
        {"item_id": 1, "status": "VERIFIED"},
        {"item_id": 2, "status": "FAILED", "error_message": "Not permitted"},
        {"item_id": 3, "status": "SKIPPED"},
        {"item_id": 4, "status": "UNKNOWN"},
    ]
    return JobResultDialog(Job(**values), items)


def _capture_item_dialog(monkeypatch, dialog: JobResultDialog):
    captured = {}

    def fake_exec(child):
        captured["title"] = child.windowTitle()
        captured["text"] = child.findChild(QPlainTextEdit).toPlainText()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    return captured


def test_view_results_lists_all_recorded_items(qapp, monkeypatch):
    dialog = _make_dialog()
    captured = _capture_item_dialog(monkeypatch, dialog)

    dialog.btn_view_results.click()

    assert captured["title"] == "Recorded Job Results"
    assert "1  ·  VERIFIED" in captured["text"]
    assert "2  ·  FAILED  ·  Not permitted" in captured["text"]
    assert "4  ·  UNKNOWN" in captured["text"]
    dialog.close()


def test_view_unverified_excludes_verified_statuses(qapp, monkeypatch):
    dialog = _make_dialog()
    captured = _capture_item_dialog(monkeypatch, dialog)

    dialog.btn_view_unverified.click()

    assert captured["title"] == "Unverified Job Results"
    assert "VERIFIED" not in captured["text"]
    assert "2  ·  FAILED" in captured["text"]
    assert "3  ·  SKIPPED" in captured["text"]
    assert "4  ·  UNKNOWN" in captured["text"]
    dialog.close()


def test_retry_delete_and_open_actions_are_connected(qapp):
    dialog = _make_dialog()
    retried = []
    deleted = []
    dialog.retryRequested.connect(retried.append)
    dialog.deleteRequested.connect(deleted.append)

    dialog.btn_retry_failed.click()
    dialog.btn_delete_history.click()
    with patch.object(dialog, "accept") as accept:
        dialog.btn_open_details.click()

    assert retried == [42]
    assert deleted == [42]
    accept.assert_called_once_with()
    dialog.close()
