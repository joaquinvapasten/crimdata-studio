@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Preparando el estudio por primera vez, toma un minuto...
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error
)
".venv\Scripts\python.exe" -m studio %*
if errorlevel 1 pause
goto :eof
:error
echo.
echo No pude preparar el entorno. Revisa que Python este instalado: https://www.python.org/downloads/
pause
