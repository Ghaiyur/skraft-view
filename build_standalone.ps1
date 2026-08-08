$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$releaseRoot = Join-Path $projectRoot "build\windows"
$templatesPath = Join-Path $projectRoot "templates"
$staticPath = Join-Path $projectRoot "static"
$managePath = Join-Path $projectRoot "manage.py"
Set-Location $projectRoot

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m pip install pyinstaller

& ".\.venv\Scripts\pyinstaller.exe" `
  --noconfirm `
  --clean `
  --name "SKRAFT View" `
  --onedir `
  --windowed `
  --distpath $releaseRoot `
  --workpath (Join-Path $projectRoot "build\work") `
  --specpath (Join-Path $projectRoot "build\spec") `
  --collect-all django `
  --collect-all psutil `
  --hidden-import wsgiref.simple_server `
  --add-data "${templatesPath};templates" `
  --add-data "${staticPath};static" `
  --add-data "${managePath};." `
  launch_skraft_view.py

Write-Host ""
Write-Host "Standalone build created in build\windows\SKRAFT View\"
