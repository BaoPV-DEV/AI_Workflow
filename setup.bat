@echo off
REM Cai dat / cap nhat thu vien (khong can winget, git hay ffmpeg cai tay)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
