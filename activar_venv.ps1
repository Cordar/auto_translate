# Activa el entorno virtual en la sesion actual.
# Hay que ejecutarlo con un punto delante:
#   . .\activar_venv.ps1
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
    return
}

. $activate
Write-Host "Entorno virtual activado." -ForegroundColor Green
Write-Host "Abre el editor con: python po_editor_gui.py" -ForegroundColor Yellow
