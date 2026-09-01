"""Regression tests for the ``dialog.Accepted`` instance-attribute bug.

PySide6 does not expose enum values (``Accepted``) as *instance* attributes on
QDialog subclasses — ``dialog.Accepted`` raises ``AttributeError``.  Every call
site must use the canonical class attribute ``QDialog.DialogCode.Accepted``.
This bug surfaced as the generic "The operation could not be completed..."
dialog when saving a campaign as a template (``SaveCampaignAsTemplateDialog``)
and when restoring a backup (``RestoreBackupDialog``).

These tests scan the source for the forbidden instance-access pattern and
verify the canonical class-attribute form works at runtime.
"""

import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files that previously used the broken `dialog.Accepted` instance access.
AFFECTED_FILES = [
    "app/main_window.py",
    "app/dialogs/invite_members_to_target_dialog.py",
    "app/dialogs/target_preparation_dialog.py",
    "app/pages/account_pool_page.py",
    "app/pages/collector_page.py",
    "app/pages/members_page.py",
    "app/pages/settings_page.py",
    "app/pages/target_groups_page.py",
]

# Matches `dialog.Accepted` where `dialog` is a local variable (instance access).
INSTANCE_ACCESS_RE = re.compile(r"\bdialog\.Accepted\b")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_no_instance_accepted_access_in_affected_files():
    """No call site may use ``dialog.Accepted`` (instance access)."""
    offenders = []
    for rel in AFFECTED_FILES:
        path = PROJECT_ROOT / rel
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if INSTANCE_ACCESS_RE.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "Instance access `dialog.Accepted` found:\n" + "\n".join(offenders)


def test_class_attribute_accepted_works_at_runtime(qapp):
    """QDialog.DialogCode.Accepted (canonical class attribute) is correct."""
    assert QDialog.DialogCode.Accepted == 1


def test_instance_attribute_accepted_raises(qapp):
    """Confirm the original failure mode: instance access raises AttributeError."""
    dialog = QDialog()
    with pytest.raises(AttributeError):
        _ = dialog.Accepted


def test_all_dialog_exec_checks_use_class_attribute():
    """Every `dialog.exec() ... Accepted` comparison must use the canonical form."""
    pattern = re.compile(r"dialog\.exec\(\)\s*(==|!=)\s*QDialog\.DialogCode\.Accepted")
    checked = 0
    for rel in AFFECTED_FILES:
        path = PROJECT_ROOT / rel
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "dialog.exec()" in line and "Accepted" in line:
                checked += 1
                assert pattern.search(line), f"Non-canonical Accepted check: {rel}: {line.strip()}"
    assert checked >= 8, f"Expected at least 8 exec()/Accepted checks, found {checked}"