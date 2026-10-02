$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
python -m pip install -r requirements-dev.txt
python -m pytest
python -m PyInstaller --noconfirm --clean packaging\VirtualTry.spec
Write-Host "Built dist\VirtualTry.exe. Models remain external under models\."
