param(
    [switch]$LaunchApp,
    [switch]$CheckLicense
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Project virtual environment not found: $Python`nCreate/install it first or run: .\scripts\build_release.ps1"
}

Push-Location $ProjectRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "== SP Telegram Windows QA =="
    & $Python -c "import sys; print('Python executable:', sys.executable); print('Python version:', sys.version)"
    & $Python -c "import PySide6, telethon, qrcode, keyring, cryptography, httpx; print('PySide6:', PySide6.__version__); print('Telethon:', telethon.__version__); print('qrcode: OK'); print('keyring: OK'); print('cryptography:', cryptography.__version__); print('httpx:', httpx.__version__)"

    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency check failed." }

    & $Python -m compileall -q app main.py scripts tests
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }

    Write-Host "== Desktop pytest suite =="
    & $Python -m pytest -q -p no:cacheprovider tests
    if ($LASTEXITCODE -ne 0) { throw "Desktop pytest suite failed." }

    Write-Host "== Isolated Qt smoke/lifecycle suite =="
    & $Python -m pytest -q -p no:cacheprovider tests/test_phase83_qt_smoke.py
    if ($LASTEXITCODE -ne 0) { throw "Qt lifecycle suite failed." }

    Write-Host "== Offscreen startup check =="
    & $Python scripts/_qa_boot_offscreen.py
    if ($LASTEXITCODE -ne 0) { throw "Offscreen startup check failed." }

    Write-Host "== Runtime workflow verification =="
    & $Python scripts/_qa_runtime_verify.py
    if ($LASTEXITCODE -ne 0) { throw "Runtime workflow verification failed." }

    Write-Host "== Release preflight =="
    if ($CheckLicense) {
        & $Python scripts/release_preflight.py --check-license
    }
    else {
        & $Python scripts/release_preflight.py
    }
    if ($LASTEXITCODE -ne 0) { throw "Release preflight failed." }

    Write-Host "QA complete."
    if ($LaunchApp) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        Write-Host "Launching SP Telegram with the project .venv..."
        & $Python main.py
    }
    else {
        Write-Host "Manual GUI review command:"
        Write-Host ".\.venv\Scripts\python.exe main.py"
    }
}
finally {
    Pop-Location
}
