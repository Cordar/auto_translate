# Editor de archivos .po

Aplicación de escritorio para Windows. Sirve para abrir un archivo gettext `.po`, revisar cada entrada y rellenar las traducciones que faltan.

Se trabaja con **un archivo cada vez**. No hay modo de línea de comandos, no traduce una carpeta entera y no genera un `.exe`.

## Requisitos

- Windows
- [Python 3.10 o superior](https://www.python.org/downloads/), con la casilla **Add python.exe to PATH** marcada. El instalador oficial incluye Tk, que es la interfaz gráfica.
- Internet, para traducir.
- Java (por ejemplo OpenJDK), solo para el botón **Corregir**. Sin Java el resto del editor funciona.
- Opcional: una clave de [DeepL](https://www.deepl.com/pro-api). Las claves gratuitas terminan en `:fx`.

El proyecto usa `polib`, `deep-translator` y `language-tool-python` (ver `requirements.txt`).

## Instalación

Abre una terminal en esta carpeta.

CMD, o doble clic en el archivo:

```bat
setup.bat
```

PowerShell:

```powershell
.\setup.ps1
```

Si PowerShell bloquea el script, permite los scripts locales de tu usuario y vuelve a lanzarlo:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Eso crea la carpeta `venv` e instala las dependencias. Si ya existe un entorno en `.venv`, los lanzadores lo usan; `setup` no lo modifica y crea `venv` si falta.

## Abrir el editor

Doble clic en `ejecutar_editor.bat`.

En PowerShell:

```powershell
.\ejecutar_editor.ps1
```

Para dejar el entorno activo y lanzar el editor a mano:

CMD:

```bat
activar_venv.bat
python po_editor_gui.py
```

PowerShell (el punto inicial es necesario):

```powershell
. .\activar_venv.ps1
python po_editor_gui.py
```

## Uso

1. Pulsa **Cargar...** y elige un `.po`.
2. Revisa **Idioma origen** e **Idioma destino**. Si la cabecera del archivo tiene `Language`, o el nombre termina en un código (`messages_es.po`), el destino se selecciona solo. Si no se reconoce, el programa pregunta.
3. Elige una entrada en la lista. El texto original está a la derecha y no se edita. La traducción sí.
4. Escribe la traducción, o pulsa **Traducir esta entrada**.
5. **Guardar** sobrescribe el archivo abierto. **Guardar como...** escribe otro. Un asterisco en el título de la ventana indica cambios sin guardar. Al salir o al abrir otro archivo, pregunta si quieres guardarlos.

La lista se ordena por la ruta que aparece en las referencias de cada entrada.

Filtros de la lista:

- texto que debe aparecer en el msgid
- **Solo sin traducir**
- **Solo a revisar**

**Pretraducir vacías** traduce las entradas que no tienen texto. No modifica las que ya tienen traducción, incluidas las marcadas `fuzzy`.

**Copiar traducciones**:

- **Idénticas**: mismo msgid. Copia la primera traducción con texto al resto de entradas iguales que estén vacías.
- **Similares**: msgid parecido al menos en un 80 %.
- **Marcar como 'a revisar'**: deja esas copias pendientes. Puedes desmarcarla si quieres copiarlas como definitivas.

Las traducciones automáticas quedan marcadas como **a revisar**. Esa marca, y de qué entrada se copió un texto, se guarda en un comentario del traductor que empieza por `POEDITOR_METADATA:`. Si borras ese comentario, el editor olvida la marca al volver a abrir el archivo.

**Corregir** revisa la traducción actual con LanguageTool, en el idioma de destino. La primera vez descarga LanguageTool: hace falta Java y puede tardar. **Limpiar** borra la traducción de la entrada abierta.

Si un comentario contiene `"Speaker": "Nombre"` o `"Context": "Nombre ->"`, ese nombre se muestra junto a la traducción.

### Plurales

Una entrada con plural se edita así:

```text
[0]: forma singular
[1]: forma plural
```

**Traducir esta entrada** y **Pretraducir vacías** rellenan `[0]` con la traducción de `msgid` y el resto de formas con la traducción de `msgid_plural`.

**Copiar traducciones** solo copia el campo `msgstr` de las entradas que no son plurales.

### Idiomas

| Nombre en el menú | Código |
| --- | --- |
| Español | `es` |
| Inglés | `en` |
| Catalán | `ca` |
| Francés | `fr` |
| Alemán | `de` |
| Italiano | `it` |
| Portugués | `pt` |

### De dónde sale la traducción

Si hay texto en **DeepL API Key**, se intenta DeepL primero.

- Clave que termina en `:fx`: API gratuita (`api-free.deepl.com`).
- Cualquier otra clave: API de pago (`api.deepl.com`).
- Con `deep-translator` 1.11.4, DeepL no incluye catalán. Ese idioma pasa al siguiente motor.

Si DeepL no está configurado o falla, se usa la página pública de Google Translate (`translate.google.com/m`), sin clave. Google responde a menudo con un bloqueo (HTTP 429 o un captcha). En ese caso el programa no se detiene: prueba MyMemory.

MyMemory no pide clave. Cada texto puede tener como máximo 500 caracteres. Un texto más largo necesita DeepL, o que Google no esté bloqueado.

La barra de estado dice qué motor ha respondido. Al terminar una pretraducción, el aviso lista los motores usados.

## Qué no hace este programa

- No traduce directorios ni busca `.po` en subcarpetas.
- No sobrescribe traducciones que ya tienen texto. Para cambiar una, edítala o pulsa **Limpiar** y vuelve a traducirla.
- No crea `AutoTranslate.exe` ni incluye `crear_ejecutable.bat`.
- No ofrece `po_translator.py`. El único programa es `po_editor_gui.py`.
