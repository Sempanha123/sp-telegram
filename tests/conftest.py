"""Shared pytest fixtures for SP-Telegram tests."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    """Provide one offscreen QApplication with isolated persistent settings."""
    settings_root = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(settings_root),
    )
    QCoreApplication.setOrganizationName("SP Telegram Tests")
    QCoreApplication.setApplicationName("SP Telegram Tests")
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def isolated_settings(qapp):
    """Clear test-only settings before and after each settings-sensitive test."""
    settings = QSettings()
    settings.clear()
    settings.sync()
    yield settings
    settings.clear()
    settings.sync()
