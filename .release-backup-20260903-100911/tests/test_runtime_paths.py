from __future__ import annotations

from pathlib import Path

import app.utils.app_paths as paths_module
from app.utils.app_paths import AppPaths, RUNTIME_DIR_ENV, default_runtime_root


def test_explicit_runtime_root(monkeypatch, tmp_path):
    target = tmp_path / "operator-data"
    monkeypatch.setenv(RUNTIME_DIR_ENV, str(target))
    assert default_runtime_root(tmp_path / "source") == target.resolve()


def test_development_runtime_root_uses_source(monkeypatch, tmp_path):
    monkeypatch.delenv(RUNTIME_DIR_ENV, raising=False)
    monkeypatch.delattr(paths_module.sys, "frozen", raising=False)
    source = tmp_path / "repo"
    assert default_runtime_root(source) == source.resolve()


def test_frozen_windows_runtime_root_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv(RUNTIME_DIR_ENV, raising=False)
    monkeypatch.setattr(paths_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    assert default_runtime_root(tmp_path / "ignored") == (
        tmp_path / "LocalAppData" / "SP Cambo" / "SP Telegram"
    ).resolve()


def test_app_paths_ensure_complete_layout(tmp_path):
    paths = AppPaths.from_root(tmp_path / "runtime")
    paths.ensure()
    expected = (
        paths.data,
        paths.sessions,
        paths.media / "campaigns",
        paths.cache / "avatars",
        paths.cache / "groups",
        paths.logs,
        paths.backups,
        paths.exports,
        paths.temp,
    )
    assert all(path.is_dir() for path in expected)
    assert paths.validate(minimum_free_bytes=1)["writable"] is True
