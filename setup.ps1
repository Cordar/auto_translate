# Script PowerShell para configurar el entorno de desarrollo
# 1. Verificar Python
# 2. Crear entorno virtual
# 3. Instalar dependencias

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

# Activar entorno virtual e instalar dependencias
Write-Host "[3/3] Instalando dependencias..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo activar el entorno virtual" -ForegroundColor Red
    Write-Host "Nota: Puede ser necesario ejecutar: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Entorno virtual activado." -ForegroundColor Green
Write-Host "Instalando paquetes desde requirements.txt..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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
Write-Host "Para usar el entorno virtual en el futuro:" -ForegroundColor Yellow
Write-Host "  1. Ejecuta: .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  2. Luego puedes usar: python po_translator.py ..." -ForegroundColor White
Write-Host ""
Read-Host "Presiona Enter para continuar"
