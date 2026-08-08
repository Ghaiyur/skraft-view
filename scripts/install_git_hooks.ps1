$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

git config core.hooksPath .githooks

Write-Host "Git hooks path set to .githooks"
Write-Host "Pre-commit hook will now run Ruff checks before each commit."
