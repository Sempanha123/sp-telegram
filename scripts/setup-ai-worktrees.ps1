$ErrorActionPreference = "Stop"

$insideWorktree = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $insideWorktree.Trim() -ne "true") {
    throw "Run this script from inside the committed sp_telegram Git repository."
}

$repositoryRoot = (git rev-parse --show-toplevel).Trim()
Set-Location $repositoryRoot

if (@(git status --porcelain).Count -ne 0) {
    throw "The working tree is not clean. Review and commit/checkpoint safe source changes first."
}

$parentDirectory = Split-Path $repositoryRoot -Parent
$codexPath = Join-Path $parentDirectory "sp_telegram-codex"
$copilotPath = Join-Path $parentDirectory "sp_telegram-copilot"

function Add-AiWorktree {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Branch
    )

    if (Test-Path $Path) {
        Write-Host "Existing folder preserved: $Path"
        return
    }

    git show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -eq 0) {
        git worktree add $Path $Branch
    }
    else {
        git worktree add $Path -b $Branch
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Could not create worktree $Path for branch $Branch."
    }
}

Add-AiWorktree -Path $codexPath -Branch "ai/codex-account-work"
Add-AiWorktree -Path $copilotPath -Branch "ai/copilot-content-work"

Write-Host ""
Write-Host "Parallel AI worktrees are ready:"
Write-Host "Codex:   $codexPath"
Write-Host "Copilot: $copilotPath"
Write-Host "Open each folder in a separate VS Code window."
