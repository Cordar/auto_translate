# Script PowerShell para ejecutar el editor avanzado de archivos .po
# Asegurate de haber ejecutado setup.ps1 primero

Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: El entorno virtual no existe. Ejecuta setup.ps1 primero." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

& "venv\Scripts\Activate.ps1"

Write-Host "Ejecutando editor de archivos .po..." -ForegroundColor Green
python po_editor_gui.py
