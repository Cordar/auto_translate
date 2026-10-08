@echo off
cd /d "%~dp0"
REM Activa el entorno virtual en esta ventana de CMD.
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: No hay entorno virtual. Ejecuta setup.bat primero.
    exit /b 1
)
echo Entorno virtual activado.
echo Abre el editor con: python po_editor_gui.py
