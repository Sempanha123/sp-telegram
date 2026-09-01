"""Capture a single page offscreen with a forced theme for pixel verification."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.application_context import ApplicationContext
from app.main_window import MainWindow
from app.theme import apply_theme

project_root = Path(".").resolve()
QCoreApplication.setOrganizationName("SP Telegram")
QCoreApplication.setApplicationName("SP Telegram")
app = QApplication(sys.argv)
app.setStyle("Fusion")
theme = sys.argv[1] if len(sys.argv) > 1 else "dark"
page = sys.argv[2] if len(sys.argv) > 2 else "dashboard"
out = sys.argv[3] if len(sys.argv) > 3 else "screenshots/qa_dark2"
QSettings().setValue("ui/theme", theme)
apply_theme(app, theme)
context = ApplicationContext(project_root)
window = MainWindow(context)
window.show()

out_dir = Path(out)
out_dir.mkdir(parents=True, exist_ok=True)


def capture():
    window.navigate(page, page.replace("_", " ").title())
    app.processEvents()
    window.grab().save(str(out_dir / f"{page}_{theme}.png"))
    print(f"Saved {out_dir / f'{page}_{theme}.png'}")
    app.quit()


QTimer.singleShot(2500, capture)
rc = app.exec()
context.close()
print("CAPTURE OK, exit code", rc)