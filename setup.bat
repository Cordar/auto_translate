@echo off
cd /d "%~dp0"
REM Script para configurar el entorno de desarrollo
REM 1. Verificar Python
REM 2. Crear entorno virtual
REM 3. Instalar dependencias

echo ========================================
echo Configuracion del Entorno de Desarrollo
echo ========================================
echo.

REM Verificar si Python esta instalado
echo [1/3] Verificando instalacion de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no esta instalado o no esta en el PATH
    echo.
    echo Por favor instala Python desde: https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion
    pause
    exit /b 1
)

python --version
echo Python encontrado correctamente!
echo.

REM Crear entorno virtual si no existe
echo [2/3] Configurando entorno virtual...
if exist "venv\" (
    echo El entorno virtual ya existe. Omitiendo creacion...
) else (
    echo Creando entorno virtual...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: No se pudo crear el entorno virtual
        pause
        exit /b 1
    )
    echo Entorno virtual creado exitosamente!
)
echo.

REM Activar entorno virtual e instalar dependencias
echo [3/3] Instalando dependencias...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: No se pudo activar el entorno virtual
    pause
    exit /b 1
)

echo Entorno virtual activado.
echo Instalando paquetes desde requirements.txt...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo.
echo ========================================
echo Configuracion completada exitosamente!
echo ========================================
echo.
echo Para abrir el editor:
echo   ejecutar_editor.bat
echo   o, en PowerShell: .\ejecutar_editor.ps1
echo.
pause
