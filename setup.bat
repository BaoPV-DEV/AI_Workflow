@echo off
REM Cài đặt lần đầu trên Windows (MX250 / máy yếu đều chạy được)
cd /d "%~dp0"
python -m venv .venv || goto :err
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -r requirements.txt || goto :err
.venv\Scripts\python -m playwright install chromium
where ffmpeg >nul 2>nul || (echo [!] Chua co ffmpeg: winget install Gyan.FFmpeg)
call vf.bat catalog
call vf.bat doctor
echo.
echo Xong. Mo Web Studio: vf studio
goto :eof
:err
echo Cai dat loi. Kiem tra Python 3.10+ da cai va co trong PATH.
