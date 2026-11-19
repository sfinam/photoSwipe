# Build a standalone Windows executable. Run from the repository root.
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install . pyinstaller
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean PhotoSwipe.spec
Write-Host "Готово: dist\PhotoSwipe.exe"
