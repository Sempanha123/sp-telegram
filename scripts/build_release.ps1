param(
    [switch]$SkipTests,
    [switch]$SkipLicenseCheck,
    [switch]$SkipExeSmokeTest,
    [switch]$NoInstall,
    [string]$CertificateThumbprint = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvRoot = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VenvRoot "Scripts\python.exe"
$DistDir = Join-Path $ProjectRoot "dist"
$ExePath = Join-Path $DistDir "SP Telegram.exe"

function New-ProjectVenv {
    Write-Host "Project .venv was not found. Creating one..."

    $created = $false
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($selector in @("-3.14", "-3.13", "-3.12", "-3")) {
            & py $selector -c "import sys; raise SystemExit(0 if sys.maxsize > 2**32 else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Creating .venv with: py $selector"
                & py $selector -m venv $VenvRoot
                if ($LASTEXITCODE -eq 0) {
                    $created = $true
                    break
                }
            }
        }
    }

    if (-not $created) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) {
            & python -c "import sys; raise SystemExit(0 if sys.maxsize > 2**32 else 1)"
            if ($LASTEXITCODE -eq 0) {
                & python -m venv $VenvRoot
                $created = ($LASTEXITCODE -eq 0)
            }
        }
    }

    if (-not $created -or -not (Test-Path $Python)) {
        throw "Could not create a 64-bit Python virtual environment. Install 64-bit Python 3.12+ and retry."
    }
}

Push-Location $ProjectRoot
try {
    Write-Host "============================================================"
    Write-Host " SP Telegram - Production Windows Release Build"
    Write-Host "============================================================"

    if (-not (Test-Path $Python)) {
        New-ProjectVenv
    }

    & $Python -c "import sys; print('Python:', sys.version); print('Executable:', sys.executable); raise SystemExit(0 if sys.maxsize > 2**32 else 1)"
    if ($LASTEXITCODE -ne 0) { throw "The release build requires 64-bit Python." }

    if (-not $NoInstall) {
        Write-Host "== Installing/updating build dependencies =="
        & $Python -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
        & $Python -m pip install -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }

    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency validation failed." }

    if (-not $SkipTests) {
        Write-Host "== Running complete desktop QA before packaging =="
        if ($SkipLicenseCheck) {
            & (Join-Path $PSScriptRoot "run_phase83_windows_qa.ps1")
        }
        else {
            & (Join-Path $PSScriptRoot "run_phase83_windows_qa.ps1") -CheckLicense
        }
    }
    else {
        Write-Host "== Tests skipped; running mandatory release preflight =="
        if ($SkipLicenseCheck) {
            & $Python scripts/release_preflight.py
        }
        else {
            & $Python scripts/release_preflight.py --check-license
        }
        if ($LASTEXITCODE -ne 0) { throw "Release preflight failed." }
    }

    Write-Host "== Generating Windows icon and version metadata =="
    & $Python scripts/generate_build_assets.py
    if ($LASTEXITCODE -ne 0) { throw "Build metadata generation failed." }

    if (Test-Path $DistDir) {
        Remove-Item $DistDir -Recurse -Force
    }

    # Strict collect mode converts duplicate collection mistakes into build
    # failures instead of silently selecting one copy.
    $OldStrictCollect = $env:PYINSTALLER_STRICT_COLLECT_MODE
    $env:PYINSTALLER_STRICT_COLLECT_MODE = "1"
    try {
        Write-Host "== Building one-file Windows executable =="
        & $Python -m PyInstaller --noconfirm --clean SPTelegram.spec
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
    }
    finally {
        if ($null -eq $OldStrictCollect) {
            Remove-Item Env:PYINSTALLER_STRICT_COLLECT_MODE -ErrorAction SilentlyContinue
        }
        else {
            $env:PYINSTALLER_STRICT_COLLECT_MODE = $OldStrictCollect
        }
    }

    if (-not (Test-Path $ExePath)) {
        throw "Build completed without the expected executable: $ExePath"
    }

    if (-not $SkipExeSmokeTest) {
        Write-Host "== Running isolated packaged-EXE lifecycle smoke test =="
        $SmokeRoot = Join-Path $ProjectRoot ".build_assets\smoke-runtime"
        if (Test-Path $SmokeRoot) { Remove-Item $SmokeRoot -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null

        $OldDataRoot = $env:SP_TELEGRAM_DATA_DIR
        $OldSmoke = $env:SP_RELEASE_SMOKE_TEST
        $OldQtPlatform = $env:QT_QPA_PLATFORM
        $env:SP_TELEGRAM_DATA_DIR = $SmokeRoot
        $env:SP_RELEASE_SMOKE_TEST = "1"
        $env:QT_QPA_PLATFORM = "offscreen"
        try {
            $Process = Start-Process -FilePath $ExePath -PassThru
            if (-not $Process.WaitForExit(20000)) {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                throw "Packaged EXE smoke test timed out."
            }
            if ($Process.ExitCode -ne 0) {
                throw "Packaged EXE smoke test failed with exit code $($Process.ExitCode)."
            }
        }
        finally {
            if ($null -eq $OldDataRoot) { Remove-Item Env:SP_TELEGRAM_DATA_DIR -ErrorAction SilentlyContinue } else { $env:SP_TELEGRAM_DATA_DIR = $OldDataRoot }
            if ($null -eq $OldSmoke) { Remove-Item Env:SP_RELEASE_SMOKE_TEST -ErrorAction SilentlyContinue } else { $env:SP_RELEASE_SMOKE_TEST = $OldSmoke }
            if ($null -eq $OldQtPlatform) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue } else { $env:QT_QPA_PLATFORM = $OldQtPlatform }
        }
        Write-Host "Packaged EXE smoke test passed."
    }

    if ($CertificateThumbprint.Trim()) {
        Write-Host "== Signing executable =="
        $SignTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if (-not $SignTool) {
            throw "Certificate thumbprint was supplied but signtool.exe is not available. Install the Windows SDK."
        }
        & $SignTool.Source sign /sha1 $CertificateThumbprint.Trim() /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $ExePath
        if ($LASTEXITCODE -ne 0) { throw "Code signing failed." }
        & $SignTool.Source verify /pa /v $ExePath
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed." }
    }

    $Version = (& $Python -c "from app.constants import APP_VERSION; print(APP_VERSION)").Trim()
    $Hash = (Get-FileHash -Algorithm SHA256 $ExePath).Hash.ToLowerInvariant()
    $Commit = "unknown"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $CommitValue = (& git rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $CommitValue) { $Commit = $CommitValue.Trim() }
    }

    $Info = @(
        "SP Telegram release",
        "version=$Version",
        "commit=$Commit",
        "sha256=$Hash",
        "built_utc=$([DateTime]::UtcNow.ToString('o'))",
        "license_api=pinned production HTTPS",
        "runtime_data=%LOCALAPPDATA%\SP Cambo\SP Telegram"
    )
    $InfoPath = Join-Path $DistDir "release-info.txt"
    $Info | Set-Content -Path $InfoPath -Encoding UTF8
    $Hash | Set-Content -Path (Join-Path $DistDir "SP Telegram.exe.sha256") -Encoding ASCII

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " RELEASE BUILD COMPLETE"
    Write-Host " EXE:    $ExePath"
    Write-Host " SHA256: $Hash"
    Write-Host " INFO:   $InfoPath"
    Write-Host "============================================================"
}
finally {
    Pop-Location
}
