"""Reproduce the campaign 'Save as Template' flow to verify the dialog.Accepted fix.

Boots the real app offscreen, opens the Create Campaign dialog, and triggers
the save-as-template handler end-to-end.  Also exercises the campaign table
refresh path to surface any QTableView-deleted errors.

Run:  python scripts/_qa_repro_campaign_error.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("SP_APP_ENV", "development")

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.theme import apply_theme

RESULTS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))
    print(RESULTS[-1])


def main() -> int:
    theme = "light"
    QSettings().setValue("ui/theme", theme)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_theme(app, theme)

    context = ApplicationContext(PROJECT_ROOT)
    window = MainWindow(context)
    window.show()

    def run():
        try:
            # --- 1. Navigate to Campaigns ---
            window.navigate("campaigns", "Campaigns")
            app.processEvents()
            check("Campaigns page navigated", True)

            # --- 2. Build the Create Campaign dialog ---
            targets, accounts = window._campaign_dialog_data()
            from app.dialogs.create_campaign_dialog import CreateCampaignDialog
            dialog = CreateCampaignDialog(
                targets, accounts, window,
                smart_planner=context.campaign_controller.plan_smart_targets,
            )
            dialog.le_campaign_name.setText("QA Repro Campaign")
            if targets:
                dialog.tbl_campaign_target_selection.selectRow(0)
            dialog.messages.append({
                "message_type": "TEXT", "type": "Text", "body": "Hello from repro",
            })
            dialog._refresh_messages()

            # --- 3. Trigger the save-as-template handler (BUG: dialog.Accepted) ---
            # Patch SaveCampaignAsTemplateDialog.exec to avoid a blocking modal.
            from app.dialogs import save_campaign_template_dialog as sctd
            original_exec = sctd.SaveCampaignAsTemplateDialog.exec
            sctd.SaveCampaignAsTemplateDialog.exec = lambda self: self.show() or 1  # 1 == Accepted
            try:
                window.on_save_campaign_as_template(dialog.data())
                check("Save-as-template handler runs without AttributeError", True)
            except AttributeError as exc:
                check("Save-as-template handler runs without AttributeError", False, repr(exc))
            except Exception as exc:  # noqa: BLE001
                check("Save-as-template handler runs without AttributeError", False, repr(exc))
            finally:
                sctd.SaveCampaignAsTemplateDialog.exec = original_exec

            # --- 4. Exercise the campaign table refresh path ---
            try:
                context.campaign_controller.refresh()
                app.processEvents()
                page = window.pages.get("campaigns")
                page._replace(context.campaign_controller.campaigns())
                app.processEvents()
                check("Campaign table refresh path clean", True)
            except RuntimeError as exc:
                check("Campaign table refresh path clean", False, repr(exc))
            except Exception as exc:  # noqa: BLE001
                check("Campaign table refresh path clean", False, repr(exc))

            # --- 5. Open campaign details dialog (has QTableView) and close it ---
            items = context.campaign_controller.campaigns()
            if items:
                try:
                    from app.dialogs.campaign_details_dialog import CampaignDetailsDialog
                    details = context.campaign_controller.details(items[0].id)
                    if details and details.get("campaign"):
                        dlg = CampaignDetailsDialog(details, window)
                        dlg.show()
                        app.processEvents()
                        dlg.close()
                        app.processEvents()
                        check("Campaign details dialog open/close clean", True)
                    else:
                        check("Campaign details dialog open/close clean", True, "no details — skipped")
                except RuntimeError as exc:
                    check("Campaign details dialog open/close clean", False, repr(exc))
                except Exception as exc:  # noqa: BLE001
                    check("Campaign details dialog open/close clean", False, repr(exc))
            else:
                check("Campaign details dialog open/close clean", True, "no campaigns — skipped")

        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("Repro completed", False, repr(exc))
        finally:
            print("\n===== REPRO SUMMARY =====")
            for r in RESULTS:
                print(r)
            passed = sum(1 for r in RESULTS if r.startswith("PASS"))
            failed = sum(1 for r in RESULTS if r.startswith("FAIL"))
            print(f"\n{passed} passed, {failed} failed")
            app.quit()

    QTimer.singleShot(2500, run)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())