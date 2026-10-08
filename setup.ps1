# Script PowerShell para configurar el entorno de desarrollo
# 1. Verificar Python
# 2. Crear entorno virtual
# 3. Instalar dependencias
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Configuracion del Entorno de Desarrollo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si Python está instalado
Write-Host "[1/3] Verificando instalacion de Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
    Write-Host "Python encontrado correctamente!" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python no esta instalado o no esta en el PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor instala Python desde: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Asegurate de marcar 'Add Python to PATH' durante la instalacion" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}
Write-Host ""

# Crear entorno virtual si no existe
Write-Host "[2/3] Configurando entorno virtual..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "El entorno virtual ya existe. Omitiendo creacion..." -ForegroundColor Yellow
} else {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: No se pudo crear el entorno virtual" -ForegroundColor Red
        Read-Host "Presiona Enter para salir"
        exit 1
    }
    Write-Host "Entorno virtual creado exitosamente!" -ForegroundColor Green
}
Write-Host ""

# Instalar dependencias con el Python del entorno virtual
Write-Host "[3/3] Instalando dependencias..." -ForegroundColor Yellow
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "ERROR: No se encontro venv\Scripts\python.exe" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Entorno virtual listo." -ForegroundColor Green
Write-Host "Instalando paquetes desde requirements.txt..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv\Scripts\python.exe" -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudieron instalar las dependencias" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Configuracion completada exitosamente!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para abrir el editor:" -ForegroundColor Yellow
Write-Host "  .\ejecutar_editor.ps1" -ForegroundColor White
Write-Host "  o doble clic en ejecutar_editor.bat" -ForegroundColor White
Write-Host ""
Read-Host "Presiona Enter para continuar"
