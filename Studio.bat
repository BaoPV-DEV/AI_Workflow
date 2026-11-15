@echo off
REM Mo AI Workflow Studio. Lan dau (chua co .venv) se tu cai dat.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:AIWF_NOLAUNCH='1'; & '%~dp0install.ps1'"
)
REM Tat Studio cu con chay tren cong 8765 (vd sau khi cap nhat code)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
".venv\Scripts\python.exe" vf.py studio
if errorlevel 1 pause
