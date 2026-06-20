# Manual de Conversión — convertir.py
## Guía completa paso a paso

---

## ¿Qué hace este script?

Toma un archivo de libro (EPUB, PDF, DOCX, etc.) y lo convierte a Markdown limpio
usando **MarkItDown** (conversión de texto, 100% local y gratuita) y **Gemini Vision**
(extracción de imágenes con contenido, requiere API key).

El script detecta automáticamente qué tipo de EPUB tienes:

- **EPUB text-based** — el texto está en HTML dentro del archivo. MarkItDown lo
  extrae directamente. Gemini Vision solo procesa las imágenes incrustadas
  (tablas de zonas, planes semanales, gráficos).

- **EPUB image-based** — todo el libro son páginas escaneadas. No hay texto
  extraíble. Gemini Vision procesa cada página completa como imagen.

- **PDF / DOCX / otros** — MarkItDown los procesa completamente de manera local.
  Gemini Vision no interviene.

---

## ¿Qué necesitas antes de empezar?

Antes de usar el script necesitas tener listo lo siguiente:

1. **Python instalado** en tu computadora (3.10 o superior).
2. **El script** `convertir.py` en tu carpeta de trabajo.
3. **El libro** que quieres convertir (`.epub`, `.pdf`, etc.).
4. **Una API key de Google Gemini** — solo si tu libro es EPUB con imágenes.
   Para EPUBs de texto puro o PDFs, la API key no es necesaria.

---

## PASO 1 — Organiza tu carpeta de trabajo

Crea una carpeta donde vivirán todos los archivos. Por ejemplo:

```
C:\Users\TuNombre\Conversion\
```

Dentro de esa carpeta coloca:
- `convertir.py` (el script)
- El libro que quieres convertir

Ejemplo de cómo debe verse:

```
Conversion\
  ├── convertir.py
  ├── Hansons First Marathon.epub
  └── Run Less Run Faster.epub
```

---

## PASO 2 — Instala las dependencias

Abre **PowerShell** y ejecuta estos comandos, uno por uno:

```powershell
pip install markitdown
```

```powershell
pip install google-genai
```

```powershell
pip install Pillow
```

```powershell
pip install pymupdf
```

Cada comando mostrará varias líneas de texto mientras instala.
Cuando termine, verás algo como `Successfully installed ...`.

> Si ves el error `pip no se reconoce`, prueba con:
> ```powershell
> python -m pip install markitdown
> python -m pip install google-genai
> python -m pip install Pillow
> ```

Solo necesitas hacer esto **una vez**. No es necesario repetirlo para cada libro.

---

## PASO 3 — Obtén tu API key de Google Gemini

La API key es la contraseña que permite al script conectarse a Gemini Vision.
Es un servicio de pago por uso, independiente de cualquier suscripción.

### 3.1 — Crea la key

1. Abre tu navegador y ve a: **https://aistudio.google.com/app/apikey**
2. Inicia sesión con tu cuenta de Google.
3. Haz clic en **"Create API key"**.
4. Selecciona un proyecto de Google Cloud (o crea uno nuevo si se te pide).
5. Copia la key que aparece. Se ve así: `AIzaSy...`

> ⚠ Guarda esta key en un lugar seguro (gestor de contraseñas, archivo de texto
> privado). No la compartas ni la subas a repositorios.

### 3.2 — Agrega créditos (billing)

La API de Gemini tiene una capa gratuita limitada. Para uso continuo:

1. Ve a: **https://console.cloud.google.com/billing**
2. Asocia una tarjeta de crédito a tu proyecto.
3. Los cargos son por uso. Una imagen procesada con Gemini Flash cuesta
   aproximadamente **$0.0002** (menos de un centavo de USD).

> Para referencia: procesar 500 imágenes cuesta aproximadamente $0.10 USD.

---

## PASO 4 — Configura la API key en PowerShell

La API key se debe configurar como variable de entorno **antes** de ejecutar el
script. Esto se hace en la misma ventana de PowerShell donde lo correrás.

Ejecuta este comando, reemplazando `TU_KEY_AQUI` con tu key real:

```powershell
$env:GEMINI_API_KEY = "AIzaSy..."
```

**Importante:** esta variable dura solo mientras esa ventana de PowerShell esté
abierta. Si cierras PowerShell y lo vuelves a abrir, debes ejecutar el comando
de nuevo antes de usar el script.

### Verificar que quedó configurada

```powershell
echo $env:GEMINI_API_KEY
```

Debe mostrar tu key. Si no muestra nada, repite el paso anterior.

---

## PASO 5 — Navega a tu carpeta de trabajo

En PowerShell, navega a la carpeta donde pusiste el script y los libros:

```powershell
cd "C:\Users\TuNombre\Conversion"
```

Verifica que el script y tu libro están ahí:

```powershell
dir
```

Debes ver `convertir.py` y el archivo del libro en la lista.

---

## PASO 6 — Ejecuta el script

### Caso A — EPUB con Vision activo (lo más común)

```powershell
python convertir.py "Hansons First Marathon.epub"
```

El script mostrará algo así mientras trabaja:

```
Gemini Vision active — model: gemini-2.5-flash
Converting 'Hansons First Marathon.epub'...
  Text-based EPUB detected.
   Processing image: training_zones.jpg
   Processing image: weekly_plan_week3.jpg
Saved as 'Hansons First Marathon.md' (284,531 characters)
```

### Caso B — EPUB con salida en archivo diferente

Usa `-o` para especificar dónde guardar el resultado:

```powershell
python convertir.py "Run Less Run Faster.epub" -o "kb\Run Less Run Faster.md"
```

> La carpeta `kb\` debe existir antes de ejecutar el comando. Si no existe, créala:
> ```powershell
> mkdir kb
> ```

### Caso C — EPUB image-based (libro completamente escaneado)

El script lo detecta automáticamente. Solo ejecutas igual que en el Caso A:

```powershell
python convertir.py "Run Less Run Faster.epub"
```

Verás este mensaje si el libro es image-based:

```
Gemini Vision active — model: gemini-2.5-flash
Converting 'Run Less Run Faster.epub'...
  Detected image-based EPUB — reading spine order...
  Pages to process: 312
  [1/312] page001.jpg
  [2/312] page002.jpg
  ...
```

> Este caso toma más tiempo porque cada página es una llamada a Gemini.
> Para un libro de 300 páginas, espera entre 15 y 30 minutos.

### Caso D — PDF con texto digital

MarkItDown extrae el texto localmente. Gemini Vision extrae las imágenes
incrustadas (tablas, gráficos, planes) y las agrega al final del `.md`:

```powershell
python convertir.py "libro.pdf"
```

```
Gemini Vision active — model: gemini-2.5-flash
Converting 'libro.pdf'...
  Text-based PDF detected.
  Processing image: page 12, image 1 (842x594px)
  Processing image: page 34, image 2 (1240x480px)
  Extracted 2 content image(s) from PDF.
Saved as 'libro.md' (198,432 characters)
```

Las imágenes OCR'd aparecen al final del archivo bajo la sección
`## Imágenes extraídas`, separadas del texto principal.

### Caso E — PDF completamente escaneado

El script lo detecta automáticamente (sin texto extraíble) y procesa
cada página como imagen:

```powershell
python convertir.py "libro_escaneado.pdf"
```

```
Gemini Vision active — model: gemini-2.5-flash
Converting 'libro_escaneado.pdf'...
  Scanned PDF detected — pages to process: 248
  [1/248] Rendering page 1/248...
  [2/248] Rendering page 2/248...
  ...
```

### Caso E — Modelo alternativo

Por defecto se usa `gemini-2.5-flash`. Para usar otro modelo:

```powershell
python convertir.py "book.epub" --model "gemini-2.5-pro"
```

---

## ¿Qué hace el script si no hay API key?

Si no configuraste `GEMINI_API_KEY` y el libro tiene imágenes, el script continúa
sin Vision. En lugar del contenido de la imagen, escribe un marcador de posición:

```
[IMAGE: training_zones.jpg]
```

El archivo `.md` resultante tendrá todo el texto del libro pero esos marcadores
en lugar de las tablas e imágenes. Puedes procesar el libro sin key para ver el
texto, y repetirlo con key cuando quieras las imágenes.

---

## Resultado esperado

El script genera un archivo `.md` en la misma carpeta del libro (o donde
especificaste con `-o`). Este archivo es el input para el siguiente paso del
pipeline: el script de extracción de KB (`extract_kb.py`).

El archivo tendrá:
- Todo el texto del libro en Markdown limpio.
- Tablas de zonas y planes semanales convertidos a tablas Markdown.
- Gráficos y diagramas descritos en prosa.
- Sin imágenes decorativas (portadas, logos, separadores).
- Sin links de navegación interna del EPUB.

---

## Errores comunes y soluciones

### `ModuleNotFoundError: No module named 'markitdown'`

Ejecuta en PowerShell:
```powershell
pip install markitdown
```

### `ModuleNotFoundError: No module named 'google.genai'`

Ejecuta en PowerShell:
```powershell
pip install google-genai
```

### `WARNING: GEMINI_API_KEY not found.`

No configuraste la variable de entorno. Ejecuta en PowerShell (en la misma ventana):
```powershell
$env:GEMINI_API_KEY = "AIzaSy..."
```

### `WARNING: Gemini Vision failed ... 429`

Superaste el límite de rate de la API. El script continúa pero esa imagen queda
como `[IMAGE: filename]`. Soluciones:
- Agrega un breve `time.sleep` entre llamadas (consulta si necesitas este ajuste).
- Verifica que tienes créditos en tu cuenta de Google Cloud.

### `ERROR: File not found`

El nombre del archivo tiene un error tipográfico, o no estás en la carpeta correcta.
Verifica con `dir` que el archivo existe y que el nombre coincide exactamente
(incluyendo mayúsculas, espacios y extensión).

### El archivo `.md` resultante está vacío

El EPUB puede tener un formato no estándar. Verifica:
1. Que el EPUB se abre correctamente en un lector (ej. Calibre).
2. Que ejecutaste el script con la ruta correcta al archivo.
3. Revisa el mensaje de salida — debe indicar cuántos caracteres se guardaron.

---

## Referencia rápida de comandos

```powershell
# Instalar dependencias (una sola vez)
pip install markitdown google-genai Pillow pymupdf

# Configurar API key (cada vez que abres PowerShell)
$env:GEMINI_API_KEY = "AIzaSy..."

# Convertir un EPUB
python convertir.py "libro.epub"

# Convertir con salida específica
python convertir.py "libro.epub" -o "kb\libro.md"

# Convertir un PDF (sin Vision)
python convertir.py "libro.pdf"

# Ver todas las opciones disponibles
python convertir.py --help
```
