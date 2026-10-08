@echo off
cd /d "%~dp0"
REM Abre el editor de archivos .po
REM Ejecuta setup.bat antes si todavia no existe el entorno virtual.

echo Activando entorno virtual...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: No hay entorno virtual. Ejecuta setup.bat primero.
    pause
    exit /b 1
)

echo Ejecutando editor de archivos .po...
python po_editor_gui.py
if %errorlevel% neq 0 (
    echo El editor termino con un error.
    pause
    exit /b %errorlevel%
)
