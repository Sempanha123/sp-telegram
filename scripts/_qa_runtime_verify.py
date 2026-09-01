"""Run isolated offscreen checks for campaign and group-detail workflows.

The script creates a disposable application root and QSettings store. It never
opens the operator database, Telegram sessions, logs, backups, or exports.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("SP_APP_ENV", "development")

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from app.application_context import ApplicationContext
from app.dialogs.create_campaign_dialog import CreateCampaignDialog
from app.dialogs.group_details_dialog import GroupDetailsDialog
from app.main_window import MainWindow
from app.models.entities import Campaign, TelegramGroup
from app.theme import apply_theme

RESULTS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    line = f"{'PASS' if ok else 'FAIL'} | {name}"
    if detail:
        line += f" | {detail}"
    RESULTS.append(line)
    print(line)


def run_checks(app: QApplication, window: MainWindow, context: ApplicationContext) -> None:
    window.navigate("campaigns", "Campaigns")
    app.processEvents()
    campaigns_page = window.pages.get("campaigns")
    check(
        "Campaigns page navigated",
        campaigns_page is not None and window.current_key() == "campaigns",
    )

    targets, accounts = window._campaign_dialog_data()
    dialog = CreateCampaignDialog(
        targets,
        accounts,
        window,
        smart_planner=context.campaign_controller.plan_smart_targets,
    )
    try:
        dialog.le_campaign_name.setText("QA Runtime Campaign")
        dialog.messages.append(
            {
                "message_type": "TEXT",
                "type": "Text",
                "body": "Hello from isolated QA runtime verification",
            }
        )
        dialog._refresh_messages()
        dialog._finish_mode = "finish"
        data = dialog.data()
        check(
            "Finish mode produces READY status",
            data.get("status") == "READY",
            f"status={data.get('status')}",
        )
    finally:
        dialog.deleteLater()

    feature_gate = context.campaign_service.feature_gate
    context.campaign_service.feature_gate = None
    try:
        try:
            context.campaign_service.create(
                {
                    "name": "",
                    "status": "READY",
                    "messages": [
                        {
                            "message_type": "TEXT",
                            "body": "Validation probe",
                        }
                    ],
                    "targets": [],
                }
            )
            check("Specific validation error", False, "No error was raised")
        except ValueError as exc:
            message = str(exc)
            check(
                "Specific validation error",
                "Campaign name is required" in message,
                message,
            )

        created = context.campaign_service.create(
            {
                "name": "QA Runtime Campaign",
                "status": "READY",
                "campaign_type": "SINGLE_POST",
                "schedule_type": "SEND_NOW",
                "messages": [
                    {
                        "message_type": "TEXT",
                        "body": "Persisted only in the disposable QA database",
                    }
                ],
                "targets": [],
            }
        )
    finally:
        context.campaign_service.feature_gate = feature_gate
    check(
        "Campaign saved with READY status",
        bool(created and created.status == "READY"),
        f"id={getattr(created, 'id', None)}, status={getattr(created, 'status', None)}",
    )

    context.campaign_controller.refresh()
    app.processEvents()
    rows = campaigns_page.model.rows if campaigns_page is not None else []
    check(
        "Saved campaign appears in table",
        any(getattr(row, "id", None) == created.id for row in rows),
        f"rows={len(rows)}",
    )

    group = context.group_repository.create(
        TelegramGroup(
            telegram_group_id=987654321,
            title="QA Runtime Group",
            username="qa_runtime_group",
            group_type="SUPERGROUP",
            access_state="PUBLIC",
            status="READY",
            member_count=42,
            is_managed=1,
        )
    )
    context.group_controller.refresh()
    app.processEvents()
    groups_page = window.pages["groups"]
    window.navigate("groups", "Groups")
    app.processEvents()
    for row, item in enumerate(groups_page.model.rows):
        if getattr(item, "id", None) == group.id:
            groups_page.table.selectRow(row)
            break

    opened = []

    def fake_exec(instance):
        opened.append(instance)
        return 0

    original_avatar_service = groups_page.avatar_service
    groups_page.avatar_service = None
    try:
        with patch.object(GroupDetailsDialog, "exec", fake_exec):
            groups_page.open_details()
        check(
            "Group details opens without TypeError",
            bool(opened),
            opened[0].windowTitle() if opened else "dialog was not opened",
        )
    except Exception as exc:
        check(
            "Group details opens without TypeError",
            False,
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        groups_page.avatar_service = original_avatar_service


def main() -> int:
    RESULTS.clear()
    with tempfile.TemporaryDirectory(prefix="sp-telegram-runtime-qa-") as tmp:
        runtime_root = Path(tmp)
        settings_root = runtime_root / "settings"
        settings_root.mkdir()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            str(settings_root),
        )
        QCoreApplication.setOrganizationName("SP Telegram QA")
        QCoreApplication.setApplicationName("SP Telegram Runtime QA")

        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        theme = "light"
        QSettings().setValue("ui/theme", theme)
        apply_theme(app, theme)

        context = None
        window = None
        try:
            context = ApplicationContext(runtime_root)
            window = MainWindow(context)
            window.show()
            app.processEvents()
            run_checks(app, window, context)
        except Exception as exc:
            check(
                "Runtime verification completed",
                False,
                f"{type(exc).__name__}: {exc}",
            )
        finally:
            if window is not None:
                window.hide()
                window.deleteLater()
                app.processEvents()
            if context is not None:
                context.close()

    failures = [result for result in RESULTS if result.startswith("FAIL")]
    print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED"))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
