# Genera dist\EditorPO\EditorPO.exe
# Quien ejecute ese .exe no necesita Python.
# El boton Corregir sigue necesitando Java instalado.
Set-Location $PSScriptRoot

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "ERROR: No hay entorno virtual. Ejecuta setup.ps1 primero." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Instalando PyInstaller..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install "pyinstaller>=6.0"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo instalar PyInstaller" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host ""
Write-Host "Creando el ejecutable. Puede tardar unos minutos..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name EditorPO --collect-submodules deep_translator --collect-all language_tool_python po_editor_gui.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo crear el ejecutable" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host ""
Write-Host "Listo: dist\EditorPO\EditorPO.exe" -ForegroundColor Green
Write-Host "Copia la carpeta dist\EditorPO completa. No basta con mover solo el .exe." -ForegroundColor Yellow
Read-Host "Presiona Enter para continuar"
