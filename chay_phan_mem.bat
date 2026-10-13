@echo off
rem Chay phan mem bao gia: tu tao moi truong .venv (lan dau) roi mo http://localhost:8000
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Dang tao moi truong Python lan dau...
    py -3.13 -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
start "" http://localhost:8000
".venv\Scripts\python.exe" run.py
goto :eof

:error
echo Loi khi cai dat moi truong. Kiem tra Python 3.13 da cai (lenh: py -0p).
pause
