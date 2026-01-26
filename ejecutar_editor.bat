@echo off
REM Script para ejecutar el editor avanzado de archivos .po
REM Asegurate de haber ejecutado setup.bat primero

echo Activando entorno virtual...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: El entorno virtual no existe. Ejecuta setup.bat primero.
    pause
    exit /b 1
)

echo Ejecutando editor de archivos .po...
python po_editor_gui.py

pause
