@echo off
REM Mo AI Workflow Studio.
REM   Studio.bat         -> mo Studio KHONG terminal (qua Studio.vbs), tu sua shortcut Desktop tro sang Studio.vbs
REM   Studio.bat debug   -> mo Studio CO terminal (xem log truc tiep khi can tim loi)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:AIWF_NOLAUNCH='1'; & '%~dp0install.ps1'"
  if not exist ".venv\Scripts\python.exe" ( pause & exit /b 1 )
)
if /i "%~1"=="debug" goto debug
REM Shortcut cu tro vao Studio.bat -> doi sang Studio.vbs (lan sau mo khong con nhay cua so den)
powershell -NoProfile -WindowStyle Hidden -Command "$l=Join-Path ([Environment]::GetFolderPath('Desktop')) 'AI Workflow Studio.lnk'; $s=New-Object -ComObject WScript.Shell; $k=$s.CreateShortcut($l); $k.TargetPath=\"$env:SystemRoot\System32\wscript.exe\"; $k.Arguments='\"%~dp0Studio.vbs\"'; $k.WorkingDirectory='%~dp0'; $k.IconLocation=\"$env:SystemRoot\System32\imageres.dll,18\"; $k.Save()"
start "" wscript.exe "%~dp0Studio.vbs"
exit /b 0

:debug
".venv\Scripts\python.exe" vf.py studio
if errorlevel 1 pause
