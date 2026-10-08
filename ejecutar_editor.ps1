# Abre el editor de archivos .po
# Ejecuta setup.ps1 antes si todavia no existe el entorno virtual.
Set-Location $PSScriptRoot

$activate = $null
foreach ($candidate in @("venv\Scripts\Activate.ps1", ".venv\Scripts\Activate.ps1")) {
    if (Test-Path $candidate) {
        $activate = $candidate
        break
    }
}

if (-not $activate) {
    Write-Host "ERROR: No hay entorno virtual. Ejecuta setup.ps1 primero." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
. $activate

Write-Host "Ejecutando editor de archivos .po..." -ForegroundColor Green
python po_editor_gui.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "El editor termino con un error." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit $LASTEXITCODE
}
