# Prepare a portable Windows folder after the PyInstaller build.
# Usage (from the repository root): .\packaging\make_portable_windows.ps1
param(
    [string]$Exe = "dist\PhotoSwipe.exe",
    [string]$OutDir = "dist\PhotoSwipePortable"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Exe)) {
    throw "Не найден $Exe. Сначала соберите приложение: pyinstaller PhotoSwipe.spec"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Copy-Item $Exe (Join-Path $OutDir "PhotoSwipe.exe") -Force
Copy-Item "packaging\portable.flag" (Join-Path $OutDir "portable.flag") -Force
Copy-Item "packaging\portable.bat" (Join-Path $OutDir "PhotoSwipe-portable.bat") -Force
Write-Host "Портативная сборка готова: $OutDir"
Write-Host "Скопируйте папку на USB-флешку и запускайте PhotoSwipe.exe."
