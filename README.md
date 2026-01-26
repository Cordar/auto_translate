# Auto Translate - Traductor Automático de Archivos .po

Herramienta en Python para traducir automáticamente archivos .po usando Google Translate.

## Características

- ✅ **Interfaz gráfica** fácil de usar (GUI)
- ✅ Traduce archivos .po completos automáticamente
- ✅ Soporte para mensajes singulares y plurales
- ✅ Procesamiento de directorios completos
- ✅ Búsqueda recursiva en subdirectorios
- ✅ Preserva metadatos del archivo .po
- ✅ Estadísticas de traducción
- ✅ Opción para sobrescribir traducciones existentes
- ✅ Puede convertirse en ejecutable .exe

## Instalación

### Opción 1: Script Automático (Recomendado)

**Windows (PowerShell):**
```powershell
.\setup.ps1
```

**Windows (CMD):**
```cmd
setup.bat
```

### Opción 2: Manual

1. **Instala Python** (si no lo tienes):
   - Descarga desde: https://www.python.org/downloads/
   - Asegúrate de marcar "Add Python to PATH" durante la instalación

2. **Crea un entorno virtual:**
```bash
python -m venv venv
```

3. **Activa el entorno virtual:**

   **Windows (PowerShell):**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   
   **Windows (CMD):**
   ```cmd
   venv\Scripts\activate.bat
   ```

4. **Instala las dependencias:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Uso

### Opción 1: Interfaz Gráfica (Recomendado para usuarios)

**Ejecutar la GUI:**

**Windows (PowerShell):**
```powershell
.\ejecutar_gui.ps1
```

**Windows (CMD):**
```cmd
ejecutar_gui.bat
```

O simplemente haz doble clic en `ejecutar_gui.bat`

La interfaz gráfica te permite:
- Seleccionar archivos .po fácilmente
- Elegir idiomas desde menús desplegables
- Ver el progreso de la traducción en tiempo real
- Ver estadísticas al finalizar

### Opción 2: Línea de Comandos

**Importante:** Asegúrate de tener el entorno virtual activado antes de usar la herramienta.

**Activar el entorno virtual:**

**Windows (PowerShell):**
```powershell
.\activar_venv.ps1
```

**Windows (CMD):**
```cmd
activar_venv.bat
```

**Traducir un archivo individual:**

```bash
python po_translator.py archivo.po --source en --target es
```

### Especificar archivo de salida

```bash
python po_translator.py archivo.po -o traducido.po --source en --target es
```

### Traducir todos los archivos .po en un directorio

```bash
python po_translator.py -d ./locale --source en --target es
```

### Traducir recursivamente en subdirectorios

```bash
python po_translator.py -d ./locale -r --source en --target es
```

### Sobrescribir traducciones existentes

```bash
python po_translator.py archivo.po --source en --target es --overwrite
```

## Opciones

- `input`: Archivo .po de entrada o directorio
- `-o, --output`: Archivo .po de salida (solo para archivos individuales)
- `-d, --directory`: Directorio con archivos .po a traducir
- `-r, --recursive`: Buscar archivos .po recursivamente en subdirectorios
- `--source, --source-lang`: Idioma origen (código ISO 639-1, default: en)
- `--target, --target-lang`: Idioma destino (código ISO 639-1, default: es)
- `--overwrite`: Sobrescribir traducciones existentes

## Códigos de Idioma

Usa códigos ISO 639-1 de dos letras para los idiomas:

- `en` - Inglés
- `es` - Español
- `fr` - Francés
- `de` - Alemán
- `it` - Italiano
- `pt` - Portugués
- `ru` - Ruso
- `zh` - Chino
- `ja` - Japonés
- `ko` - Coreano
- Y muchos más...

## Ejemplo

```bash
# Traducir un archivo de inglés a español
python po_translator.py messages.po --source en --target es

# El archivo se guardará como messages_es.po
```

## Notas

- La herramienta usa Google Translate API (gratuita) a través de la biblioteca `deep-translator`
- Las traducciones existentes se preservan por defecto (usa `--overwrite` para sobrescribirlas)
- Los metadatos del archivo .po se actualizan automáticamente
- Para textos muy largos (>5000 caracteres), se dividen en partes para evitar errores

## Crear Ejecutable (.exe)

Si quieres crear un ejecutable independiente que no requiera Python instalado:

```bash
crear_ejecutable.bat
```

Esto creará un archivo `dist\AutoTranslate.exe` que puedes ejecutar directamente con doble clic.

**Nota:** El ejecutable será más grande (~50-100 MB) porque incluye Python y todas las dependencias.

## Requisitos

- Python 3.6+
- polib
- deep-translator
- tkinter (incluido con Python en la mayoría de instalaciones)

## Licencia

Este proyecto es de código abierto y está disponible para uso libre.
