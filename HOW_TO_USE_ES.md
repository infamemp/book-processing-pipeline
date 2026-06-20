# Cómo usar este pipeline — Guía paso a paso

Esta guía asume que no recuerdas nada de cómo funciona esto. Sigue los pasos en
orden, sin saltarte ninguno. Cada paso te dice exactamente qué hacer, qué escribir,
y qué deberías ver en pantalla.

---

## Antes de empezar — ¿Qué necesitas tener listo?

- [ ] Google Drive instalado y sincronizado en esta computadora
- [ ] La carpeta del repositorio descargada en esta computadora (ya sea en
      `C:\Dev\Github\book-processing-pipeline` o `E:\Dev\github\book-processing-pipeline`,
      según la máquina)
- [ ] La variable de entorno `GEMINI_API_KEY` configurada (solo necesaria si vas
      a convertir libros con imágenes)
- [ ] La variable de entorno `ANTHROPIC_API_KEY` configurada (necesaria para extraer KB)

Si no sabes si esas variables están configuradas, ve a la sección
[Verificar que las API keys están configuradas](#verificar-que-las-api-keys-están-configuradas)
al final de este documento.

---

## PARTE 1 — Cómo abrir la terminal correcta

Todo lo que vas a hacer en esta guía se ejecuta desde **una sola carpeta**, siempre
la misma, sin importar qué paso del proceso estés haciendo.

### Paso 1.1 — Abre el explorador de archivos de Windows

### Paso 1.2 — Navega a la carpeta del repositorio

Ve a esta ruta (la que exista en tu computadora — solo una de las dos):
```
C:\Dev\Github\book-processing-pipeline
```
o
```
E:\Dev\github\book-processing-pipeline
```

### Paso 1.3 — Abre una terminal ahí

Dentro de esa carpeta (sin entrar a ninguna subcarpeta), haz **clic derecho** en
un espacio vacío (no sobre ningún archivo) y selecciona:

> **Abrir en Terminal**

(En algunas versiones de Windows dice "Abrir ventana de PowerShell aquí".)

Se va a abrir una ventana negra o azul oscuro con texto. Esa es tu terminal.
Verifica que en la primera línea diga algo parecido a:
```
PS C:\Dev\Github\book-processing-pipeline>
```
Si dice esa ruta, estás en el lugar correcto. **Deja esta ventana abierta** — la
vas a usar para todos los pasos de esta guía.

---

## PARTE 2 — Convertir un libro nuevo (Paso 1 del pipeline)

### Paso 2.1 — Pon el archivo del libro en la carpeta de entrada

Abre el explorador de Windows y ve a tu Google Drive, a la carpeta:
```
00_Anthropic\_source_intake
```

Copia o arrastra ahí el archivo del libro que quieres procesar (`.epub` o `.pdf`).

**Anota el nombre exacto del archivo, tal como aparece**, incluyendo mayúsculas,
espacios y la extensión. Por ejemplo: `Daniels Running Formula.epub`

### Paso 2.2 — Decide el nombre que le darás a este libro

Vas a inventar un nombre corto para identificar este libro en las carpetas. Reglas:
- Todo en minúsculas
- Sin espacios (usa guiones `-` en su lugar)
- Sin acentos ni símbolos raros

Ejemplo: si el libro es "Daniels Running Formula", el nombre sería:
```
daniels-running-formula
```

### Paso 2.3 — Ve a la terminal que dejaste abierta (Parte 1)

Escribe el siguiente comando, **reemplazando** los dos valores entre comillas con
los tuyos:

```powershell
.\step1_convert.ps1 -BookName "daniels-running-formula" -SourceFile "Daniels Running Formula.epub"
```

- `-BookName` → el nombre corto que inventaste en el Paso 2.2
- `-SourceFile` → el nombre exacto del archivo, tal como lo anotaste en el Paso 2.1

Presiona **Enter**.

### Paso 2.4 — Qué vas a ver en pantalla

El script va a mostrar varias líneas de texto. Esto es normal y esperado:

```
=== STEP 1: CONVERT ===
Book name   : daniels-running-formula
Source file : Daniels Running Formula.epub
Drive root  : E:\Mi Unidad\00_Anthropic

[OK] Found source file in _source_intake.
[OK] Created new book folder in Library: daniels-running-formula
[OK] Moved file to:
  ...\00_original\Daniels Running Formula.epub

Running convert.py...

Gemini Vision active — model: gemini-2.5-flash
Converting 'Daniels Running Formula.epub'...
  ...
Saved as '...md' (284,531 characters)

=== DONE ===
Converted file saved at:
  ...\01_converted\Daniels Running Formula.md
```

Esto puede tardar desde unos segundos hasta 20-30 minutos, dependiendo de cuántas
imágenes tenga el libro. **No cierres la terminal mientras esté trabajando.**

### Paso 2.5 — Si ves un error en vez de "DONE"

| Si ves esto... | Significa esto... | Qué hacer |
|---|---|---|
| `ERROR: File not found in _source_intake` | El nombre que escribiste en `-SourceFile` no coincide exactamente con el archivo | Verifica mayúsculas, espacios y extensión. Revisa que el archivo esté realmente en `_source_intake` |
| `ERROR: convert.py not found` | Estás en la carpeta equivocada | Repite la Parte 1 — asegúrate de abrir la terminal dentro de la carpeta del repositorio |
| `ERROR: Could not find the '00_Anthropic' folder` | Google Drive no está sincronizado en esta máquina | Abre la app de Google Drive y espera a que sincronice |
| Algo menciona `GEMINI_API_KEY` | Falta configurar la API key de Gemini | Ve a [Verificar que las API keys están configuradas](#verificar-que-las-api-keys-están-configuradas) |

### Paso 2.6 — Verifica el resultado

Ve a tu Google Drive, a:
```
00_Anthropic\Library\daniels-running-formula\01_converted\
```
Debería haber ahí un archivo `.md` con el contenido del libro. Ábrelo y échale un
ojo rápido para confirmar que se ve bien.

**Ya terminaste el Paso 1 para este libro.** No necesitas hacer nada más en este
momento — puedes seguir al Paso 2 ahora, o cerrar todo y volver otro día.

---

## PARTE 3 — Extraer el conocimiento del libro (Paso 2 del pipeline)

Este paso toma el archivo `.md` que generaste en la Parte 2 y le pide a la IA que
extraiga la metodología, filosofía y datos técnicos del libro, en un formato
estructurado.

### Paso 3.1 — Ve a la terminal (misma de siempre)

Si la cerraste, repite la Parte 1 para abrir una nueva.

### Paso 3.2 — Escribe el comando

```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Mode immediate
```

- `-BookName` → el mismo nombre corto que usaste en la Parte 2 (debe ser idéntico)
- `-Mode` → escribe `immediate` si quieres el resultado ahora mismo (más caro), o
  `batch` si no tienes prisa y quieres pagar menos (tarda hasta 24 horas)

Presiona **Enter**.

### Paso 3.3 — Qué vas a ver en pantalla (modo immediate)

```
=== STEP 2: EXTRACT KB ===
Book name  : daniels-running-formula
Drive root : E:\Mi Unidad\00_Anthropic

Action     : SUBMIT EXTRACTION
Mode       : immediate
Input file : Daniels Running Formula.md

[1/1] Daniels Running Formula
  Input ~45,000 tokens  |  Costo est. ~$1.20
  Procesando... listo  180s  in=44,892  out=38,201  $1.15

=== DONE ===
KB file saved into:
  ...\02_kb\
```

Esto puede tardar varios minutos. Sé paciente y no cierres la ventana.

### Paso 3.4 — Qué vas a ver en pantalla (modo batch)

```
=== STEP 2: EXTRACT KB ===
Action     : SUBMIT EXTRACTION
Mode       : batch
...
Batch ID  : msgbatch_abc123xyz
...
=== DONE ===
Batch submitted. Look above for the Batch ID, then check it later with:
  .\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123xyz"
```

**Copia y guarda ese Batch ID en algún lado** (un Notepad, por ejemplo). Lo vas a
necesitar para revisar el resultado más tarde.

### Paso 3.5 — Si elegiste batch: cómo revisar el resultado después

Espera al menos un par de horas (puede tardar hasta 24h). Luego, en la terminal:

```powershell
.\step2_extract.ps1 -BookName "daniels-running-formula" -Check "msgbatch_abc123xyz"
```
(usa el Batch ID real que copiaste en el Paso 3.4)

Si todavía no está listo, vas a ver algo como:
```
Estado : in_progress
Aún no está listo. Vuelve a consultar con: ...
```
Eso es normal, simplemente espera más e intenta de nuevo después.

Si ya está listo, el archivo se descarga automáticamente y verás "DONE".

### Paso 3.6 — Si ves un error

| Si ves esto... | Significa esto... | Qué hacer |
|---|---|---|
| `ERROR: Book folder not found in Library` | El nombre del libro no coincide con ninguna carpeta existente | Verifica que escribiste el mismo `-BookName` que usaste en la Parte 2 |
| `ERROR: No .md file found in 01_converted` | No completaste la Parte 2 para este libro | Vuelve a la Parte 2 y corre `step1_convert.ps1` primero |
| `ERROR: Found more than one .md file` | Hay más de un archivo `.md` en esa carpeta | Entra a `01_converted` y deja solo el archivo correcto, mueve o borra el resto |
| Algo menciona `ANTHROPIC_API_KEY` | Falta configurar esa API key | Ve a [Verificar que las API keys están configuradas](#verificar-que-las-api-keys-están-configuradas) |

### Paso 3.7 — Verifica el resultado

Ve a:
```
00_Anthropic\Library\daniels-running-formula\02_kb\
```
Debería haber un archivo `.md` con el conocimiento extraído del libro, organizado
en secciones.

---

## PARTE 4 — Combinar varios libros del mismo autor (Paso 3 del pipeline)

Este paso es opcional — solo lo necesitas si quieres juntar el conocimiento de
varios libros (normalmente del mismo autor) en un solo archivo.

### Paso 4.1 — La primera vez: crea la carpeta de trabajo temporal

En la terminal, escribe:
```powershell
.\step3_combine.ps1 -OutputName "prueba.md"
```
(el nombre no importa todavía, en este primer intento solo se va a crear una carpeta)

Vas a ver:
```
[OK] Created staging folder (first time): ...\combinados\_staging
Nothing to combine yet. Copy your KB .md files into that folder...
```

Esto es normal y esperado la primera vez. Ya se creó la carpeta que necesitas.

### Paso 4.2 — Copia ahí los archivos que quieres combinar

Ve a Google Drive, a:
```
00_Anthropic\combinados\_staging\
```

Ahora ve a las carpetas `02_kb` de cada libro que quieras combinar, y **copia**
(no muevas) esos archivos `.md` dentro de `_staging`.

### Paso 4.3 — Renombra los archivos para definir el orden

Dentro de `_staging`, **cambia el nombre** de cada archivo agregando un número al
principio, según el orden en que quieres que aparezcan en el resultado final:

```
01_daniels-book-one_kb.md
02_daniels-book-two_kb.md
03_daniels-book-three_kb.md
```

El número decide el orden — `01_` aparece primero, `02_` segundo, y así sucesivamente.

### Paso 4.4 — Corre el script de combinar

En la terminal:
```powershell
.\step3_combine.ps1 -OutputName "daniels_combined.md"
```

Cambia `"daniels_combined.md"` por el nombre que quieras darle al archivo final.

### Paso 4.5 — Qué vas a ver en pantalla

```
=== STEP 3: COMBINE ===
Output name : daniels_combined.md
...
[OK] Found 3 file(s) in staging:
  - 01_daniels-book-one_kb.md
  - 02_daniels-book-two_kb.md
  - 03_daniels-book-three_kb.md

Running combine.py...
...
=== DONE ===
Combined file saved at:
  ...\combinados\daniels_combined.md

Staging folder has been emptied and is ready for the next combination.
```

### Paso 4.6 — Verifica el resultado

Ve a:
```
00_Anthropic\combinados\
```
Ahí debe estar tu archivo combinado, listo para subir a Claude Projects, Gemini o ChatGPT.

**Nota:** después de cada combinación exitosa, la carpeta `_staging` se vacía
sola — así queda lista para la próxima vez sin que tengas que limpiarla a mano.

### Paso 4.7 — Si ves un error

| Si ves esto... | Significa esto... | Qué hacer |
|---|---|---|
| `ERROR: No .md files found in staging folder` | No copiaste ningún archivo en `_staging`, o ya se había vaciado de una corrida anterior | Repite el Paso 4.2 |

---

## Verificar que las API keys están configuradas

Las API keys se configuran como variables de entorno **permanentes** de Windows.
Si ya las configuraste antes, deberían seguir funcionando sin que hagas nada.

### Para verificar si ya están configuradas

En la terminal, escribe:
```powershell
echo $env:GEMINI_API_KEY
echo $env:ANTHROPIC_API_KEY
```

Si cada una muestra una clave larga de texto (algo como `AIzaSy...` o `sk-ant-...`),
ya están configuradas correctamente y no necesitas hacer nada más.

Si alguna no muestra nada (línea vacía), necesitas configurarla:

### Para configurar GEMINI_API_KEY de forma permanente

```powershell
[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'AIzaSy...', 'User')
```
(reemplaza `AIzaSy...` con tu key real)

### Para configurar ANTHROPIC_API_KEY de forma permanente

```powershell
[System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-ant-...', 'User')
```
(reemplaza `sk-ant-...` con tu key real)

**Importante:** después de configurar una variable nueva, debes **cerrar la
terminal y abrir una nueva** para que el cambio tenga efecto. Las terminales que
ya estaban abiertas no se actualizan solas.

---

## Resumen de comandos (referencia rápida)

```powershell
# Paso 1 — Convertir
.\step1_convert.ps1 -BookName "nombre-libro" -SourceFile "Nombre Exacto.epub"

# Paso 2 — Extraer KB (inmediato)
.\step2_extract.ps1 -BookName "nombre-libro" -Mode immediate

# Paso 2 — Extraer KB (económico, 24h)
.\step2_extract.ps1 -BookName "nombre-libro" -Mode batch

# Paso 2 — Revisar un batch pendiente
.\step2_extract.ps1 -BookName "nombre-libro" -Check "msgbatch_xxxxx"

# Paso 3 — Combinar (después de copiar y renombrar archivos en _staging)
.\step3_combine.ps1 -OutputName "nombre_final.md"
```
