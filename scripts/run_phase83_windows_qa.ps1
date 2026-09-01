param(
    [switch]$LaunchApp
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Project virtual environment not found: $Python`nCreate it with: py -3.14 -m venv .venv"
}

Push-Location $ProjectRoot
try {
    Write-Host "== Phase 8.3 Windows QA =="
    & $Python -c "import sys; print('Python executable:', sys.executable); print('Python version:', sys.version)"
    & $Python -c "import PySide6, telethon, qrcode, keyring; print('PySide6:', PySide6.__version__); print('Telethon:', telethon.__version__); print('qrcode: OK'); print('keyring:', getattr(keyring, '__version__', 'OK'))"
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency check failed." }
    & $Python -m compileall -q app license_server main.py scripts tests
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
    & $Python -m pytest -q -p no:cacheprovider tests
    if ($LASTEXITCODE -ne 0) { throw "Desktop pytest suite failed." }

    Write-Host "== Isolated Qt smoke/lifecycle suite =="
    & $Python -m pytest -q -p no:cacheprovider tests/test_phase83_qt_smoke.py
    if ($LASTEXITCODE -ne 0) { throw "Qt lifecycle suite failed." }

    Write-Host "== License-service tests =="
    & $Python -m pytest -q -p no:cacheprovider license_server/tests
    if ($LASTEXITCODE -ne 0) { throw "License-service tests failed." }
    & $Python scripts/_qa_boot_offscreen.py
    if ($LASTEXITCODE -ne 0) { throw "Offscreen startup check failed." }
    & $Python scripts/_qa_runtime_verify.py
    if ($LASTEXITCODE -ne 0) { throw "Runtime workflow verification failed." }

    if ($LaunchApp) {
        Write-Host "Launching SP Telegram with the project .venv..."
        & $Python main.py
    } else {
        Write-Host "QA complete. To perform manual GUI/log/terminal review run:"
        Write-Host ".\.venv\Scripts\python.exe main.py"
    }
}
finally {
    Pop-Location
}
