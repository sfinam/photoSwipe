@echo off
rem Put this file next to PhotoSwipe.exe. Settings and cache will be stored in
rem the PhotoSwipeData folder beside the executable.
setlocal
set "PHOTOSWIPE_DATA_DIR=%~dp0PhotoSwipeData"
start "" "%~dp0PhotoSwipe.exe"
