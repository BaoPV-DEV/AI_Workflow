@echo off
REM Mo AI Workflow Studio. Lan dau (chua co .venv) se tu cai dat.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:AIWF_NOLAUNCH='1'; & '%~dp0install.ps1'"
)
".venv\Scripts\python.exe" vf.py studio
if errorlevel 1 pause
