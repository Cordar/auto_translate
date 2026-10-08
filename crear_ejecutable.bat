@echo off
cd /d "%~dp0"
REM Genera dist\EditorPO\EditorPO.exe
REM Quien ejecute ese .exe no necesita Python.
REM El boton Corregir sigue necesitando Java instalado.

if not exist "venv\Scripts\python.exe" (
    echo ERROR: No hay entorno virtual. Ejecuta setup.bat primero.
    pause
    exit /b 1
)

echo Instalando PyInstaller...
venv\Scripts\python.exe -m pip install "pyinstaller>=6.0"
if %errorlevel% neq 0 (
    echo ERROR: No se pudo instalar PyInstaller
    pause
    exit /b 1
)

echo.
echo Creando el ejecutable. Puede tardar unos minutos...
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name EditorPO --collect-submodules deep_translator --collect-all language_tool_python po_editor_gui.py
if %errorlevel% neq 0 (
    echo ERROR: No se pudo crear el ejecutable
    pause
    exit /b 1
)

echo.
echo Listo: dist\EditorPO\EditorPO.exe
echo Copia la carpeta dist\EditorPO completa. No basta con mover solo el .exe.
pause
