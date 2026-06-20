# Manual de Extracción de KB
## Guía completa paso a paso — v2.2

---

## ¿Qué hace este sistema?

Toma un libro de entrenamiento convertido a Markdown y extrae una base de
conocimiento (KB) estructurada usando tu prompt de extracción. El libro
entra completo en una sola llamada a la API de Claude. Sin límites de
sesión, sin pérdida de contexto, sin interrupciones.

El resultado es un archivo `.md` con el KB listo para usar en tu sistema
de coaching.

---

## Lo que necesitas antes de empezar

| # | Qué | ¿Ya lo tienes? |
|---|---|---|
| 1 | Python instalado en tu computadora | ✓ |
| 2 | El script `extract_kb.py` descargado | ✓ |
| 3 | Tu prompt de extracción guardado como `extraction_prompt.md` | ✓ |
| 4 | El libro convertido a `.md` por MarkItDown | ✓ |
| 5 | Una API key de Anthropic | ← Este manual te guía a obtenerla |

---

## CONFIGURACIÓN INICIAL

Estos pasos se hacen **una sola vez**. No es necesario repetirlos para
cada libro.

---

## PASO 1 — Organiza tu carpeta de trabajo

**Paso 1.** Crea una carpeta en tu computadora. Puedes llamarla
`KB Extraction` y ponerla donde quieras. Por ejemplo:

```
E:\Mi Unidad\00_Anthropic\KB Extraction\
```

**Paso 2.** Copia estos archivos dentro de esa carpeta:
- `extract_kb.py`
- `extraction_prompt.md`
- Los libros `.md` que quieres procesar

**Paso 3.** Verifica que tu carpeta se vea así:

```
KB Extraction\
  ├── extract_kb.py
  ├── extraction_prompt.md
  ├── Run Less Run Faster.md
  └── (otros libros .md)
```

---

## PASO 2 — Instala el SDK de Anthropic

El SDK es una librería que permite que el script se comunique con la API
de Claude.

**Paso 1.** Abre PowerShell. Para abrirlo, presiona `Windows + R`,
escribe `powershell` y presiona Enter.

**Paso 2.** Ejecuta este comando:

```powershell
pip install anthropic
```

**Paso 3.** Espera a que termine. Verás varias líneas de texto instalándose.
Al final debe aparecer una línea como esta:

```
Successfully installed anthropic-X.X.X
```

> Si ves el error `pip no se reconoce`, prueba con:
> ```powershell
> python -m pip install anthropic
> ```

> Si ves el error `python no se reconoce`, Python no está configurado
> correctamente. Reinstálalo desde **python.org** y durante la instalación
> marca la opción **"Add Python to PATH"**.

---

## PASO 3 — Obtén tu API key de Anthropic

La API key es una contraseña que permite que el script se conecte a Claude.
Es distinta a tu suscripción de claude.ai — funciona como una cuenta
separada de pago por uso.

### Cómo crear la API key

**Paso 1.** Abre tu navegador y ve a: **https://console.anthropic.com**

**Paso 2.** Inicia sesión con tu cuenta de Anthropic.

**Paso 3.** En el menú de la izquierda, haz clic en **"API Keys"**.

**Paso 4.** Haz clic en el botón **"Create Key"**.

**Paso 5.** Escribe un nombre para identificarla, por ejemplo: `kb-extraction`.
Luego haz clic en **"Create Key"**.

**Paso 6.** Aparecerá tu key. Se ve así: `sk-ant-api03-...`

Cópiala y guárdala en un lugar seguro (por ejemplo, en un archivo de
texto en tu computadora).

> ⚠ Anthropic solo muestra la key una vez. Si la cierras sin copiarla,
> tendrás que crear una nueva.

### Cómo agregar créditos para usar la API

Sin créditos el script no funcionará. Sigue estos pasos para cargar saldo:

**Paso 1.** En el mismo sitio (console.anthropic.com), haz clic en
**"Settings"** en el menú izquierdo.

**Paso 2.** Haz clic en **"Billing"**.

**Paso 3.** Haz clic en **"Add Credits"**.

**Paso 4.** Elige el monto. Con **$10 USD** puedes procesar entre 5 y 10
libros usando Opus. Con **$5 USD** puedes procesar entre 5 y 8 libros
usando Sonnet.

---

## PASO 4 — Configura la API key en PowerShell

Hay dos formas de configurarla. La **Forma A** es rápida pero dura solo
mientras PowerShell esté abierto. La **Forma B** la guarda de forma
permanente para que no tengas que repetirlo nunca más.

Haz primero la Forma A para verificar que todo funciona, y luego la
Forma B para guardarla permanentemente.

---

### PASO 4A — Configuración temporal

Abre PowerShell y ejecuta este comando. Reemplaza el texto entre comillas
con tu key real:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

No verás ninguna respuesta — eso es normal. La key quedó configurada
para esta sesión.

Para verificar que se guardó correctamente, ejecuta:

```powershell
echo $env:ANTHROPIC_API_KEY
```

Debe mostrar tu key completa en pantalla.

> ⚠ Esta configuración se borra al cerrar PowerShell. Cada vez que
> abras PowerShell deberás repetir este comando, a menos que hagas
> la Forma B a continuación.

---

### PASO 4B — Configuración permanente

Esto guarda la key en un archivo que PowerShell carga automáticamente
cada vez que lo abres.

**Paso 1.** Habilita la ejecución de scripts en PowerShell.

Windows bloquea la ejecución de scripts por seguridad. Ejecuta este
comando para habilitarlo:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

PowerShell te preguntará si confirmas. Escribe `S` y presiona Enter:

```
¿Deseas cambiar la directiva de ejecución?
[S] Sí  [O] Sí a todo  [N] No  [T] No a todo  [?] Ayuda
(el valor predeterminado es "N"): S
```

> Si no aparece ninguna pregunta y regresa directamente al prompt `PS>`,
> está bien — significa que ya estaba habilitado.

**Paso 2.** Crea el archivo de perfil de PowerShell:

```powershell
New-Item -Path $PROFILE -Type File -Force
```

Verás una respuesta como esta — es normal:

```
    Directory: E:\Documentos\WindowsPowerShell

Mode                LastWriteTime    Length  Name
----                -------------    ------  ----
-a----   18/06/2026   ...                 0  Microsoft.PowerShell_profile.ps1
```

**Paso 3.** Abre ese archivo con Notepad:

```powershell
notepad $PROFILE
```

Se abre Notepad con el archivo vacío.

**Paso 4.** Escribe esta línea en Notepad. Reemplaza el texto entre
comillas con tu key real:

```
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Así debe verse el archivo:

```
$env:ANTHROPIC_API_KEY="sk-ant-api03-..."
```

**Paso 5.** Guarda el archivo con `Ctrl + S` y cierra Notepad.

**Paso 6.** Cierra PowerShell completamente y vuelve a abrirlo.

**Paso 7.** Verifica que la key cargó automáticamente:

```powershell
echo $env:ANTHROPIC_API_KEY
```

Debe mostrar tu key completa. A partir de ahora no necesitas configurarla
manualmente nunca más.

---

## PASO 5 — Abre PowerShell en tu carpeta de trabajo

Antes de correr el script, PowerShell debe estar ubicado dentro de tu
carpeta `KB Extraction`. Así el script encuentra los archivos
correctamente.

**Paso 1.** Abre el Explorador de Windows.

**Paso 2.** Navega hasta tu carpeta `KB Extraction`.

**Paso 3.** Haz clic derecho en un espacio vacío dentro de la carpeta
(no sobre ningún archivo).

**Paso 4.** Selecciona **"Abrir en Terminal"** o **"Open in Terminal"**.

Se abre PowerShell. Verifica que la ruta que aparece corresponde a tu
carpeta:

```
PS E:\Mi Unidad\00_Anthropic\KB Extraction>
```

> Si no aparece la opción "Abrir en Terminal", abre PowerShell
> normalmente y navega a tu carpeta con este comando (ajusta la ruta):
> ```powershell
> cd "E:\Mi Unidad\00_Anthropic\KB Extraction"
> ```

---

## USO DEL SISTEMA

A partir de aquí, esto es lo que harás cada vez que quieras procesar
un libro. La configuración inicial ya está hecha.

Elige el caso que corresponde a tu necesidad:

---

## CASO A — Un libro, resultado inmediato

Usa esto cuando necesitas el KB ahora mismo.

**Paso 1.** Abre PowerShell en tu carpeta de trabajo (ver PASO 5).

**Paso 2.** Copia este comando en PowerShell. Solo debes cambiar dos cosas:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "NOMBRE_DEL_LIBRO.md" --output kb_out --model MODELO
```

| Valor en MAYÚSCULAS | Qué escribir |
|---|---|
| `NOMBRE_DEL_LIBRO.md` | El nombre exacto de tu archivo .md con su extensión |
| `MODELO` | `opus` para libros con tablas densas · `sonnet` para libros narrativos |

**Ejemplo:**

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --model opus
```

> **Opcional:** Si quieres que el KB incluya título, autor y edición en los
> tags `[SRC:]`, agrega `--book-meta` al final:
> ```powershell
> python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --model opus --book-meta "Run Less Run Faster | Pierce, Murr, Moss | 3rd ed. 2014"
> ```

**Paso 3.** Presiona Enter. El proceso tarda entre 2 y 5 minutos.
No cierres PowerShell mientras corre.

Verás esto en pantalla:

```
============================================================
  Modo   : INMEDIATO
  Modelo : claude-opus-4-8
  Libros : 1
    • Run Less Run Faster  (~159,000 tokens)
  Salida : kb_out
============================================================

[1/1] Run Less Run Faster
  Input ~162,000 tokens  |  Costo est. ~$2.50
  Procesando... listo  187s  in=162,431  out=48,203  $2.41
  → kb_out\run-less-run-faster_kb.md
```

Cuando aparece la palabra `listo` seguida de `→ kb_out\...` el proceso
terminó correctamente.

**Paso 4.** Abre el Explorador de Windows y navega a tu carpeta
`KB Extraction`. Ahí verás una nueva carpeta llamada `kb_out`. Dentro
está tu archivo KB con el nombre del libro seguido de `_kb.md`.

Para abrir el archivo, haz doble clic sobre él. Se abrirá con el
programa predeterminado para archivos `.md` (Notepad, VS Code, etc.).

---

**¿Quieres usar Sonnet en lugar de Opus?**

Agrega `--model sonnet` al final del comando:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --book-meta "Run Less Run Faster | Pierce, Murr, Moss | 3rd ed. 2014" --model sonnet
```

---

## CASO B — Un libro, entrega en ~24 horas (50% más barato)

Usa esto cuando no tienes prisa. El resultado es idéntico al Caso A,
pero cuesta la mitad y llega en máximo 24 horas.

**Paso 1.** Abre PowerShell en tu carpeta de trabajo (ver PASO 5).

**Paso 2.** Copia este comando y cambia solo dos valores:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "NOMBRE_DEL_LIBRO.md" --output kb_out --mode batch --model MODELO
```

| Valor en MAYÚSCULAS | Qué escribir |
|---|---|
| `NOMBRE_DEL_LIBRO.md` | El nombre exacto de tu archivo .md con su extensión |
| `MODELO` | `opus` para libros con tablas densas · `sonnet` para libros narrativos |

**Ejemplo:**

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --mode batch --model opus
```

> **Opcional:** Para incluir título, autor y edición en los tags `[SRC:]`:
> ```powershell
> python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --mode batch --model opus --book-meta "Run Less Run Faster | Pierce, Murr, Moss | 3rd ed. 2014"
> ```

**Paso 3.** Presiona Enter. El script termina en segundos — solo envía
el libro a Anthropic para que lo procese en segundo plano.

Verás esto en pantalla:

```
Preparando 1 libro(s) para el Batch API...

  Run Less Run Faster    ~162,000 tokens  ~$1.25

  Costo estimado : ~$1.25 USD (50% desc. Batch API)
  Entrega        : máximo 24 horas

Enviando... enviado.

============================================================
  Batch ID  : msgbatch_01abc123xyz...
  Info      : kb_out\batch_pending.json
============================================================
```

**Paso 4.** Anota o copia el **Batch ID** que aparece en pantalla
(la línea que empieza con `msgbatch_`). Lo necesitas para descargar
el resultado.

> El Batch ID también queda guardado automáticamente en el archivo
> `kb_out\batch_pending.json` por si lo necesitas después.

**Paso 5.** Cuando hayan pasado unas horas (máximo 24), descarga el
resultado siguiendo el **CASO D**.

---

**¿Quieres usar Sonnet en lugar de Opus?**

Agrega `--model sonnet` al final del comando:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "Run Less Run Faster.md" --output kb_out --mode batch --book-meta "Run Less Run Faster | Pierce, Murr, Moss | 3rd ed. 2014" --model sonnet
```

---

## CASO C — Varios libros a la vez, entrega en ~24 horas

Usa esto cuando tienes múltiples libros y quieres enviarlos todos de
una sola vez.

**Paso 1.** Dentro de tu carpeta `KB Extraction`, crea una subcarpeta
llamada `libros`.

Para crearla desde PowerShell:

```powershell
mkdir libros
```

O créala manualmente desde el Explorador de Windows haciendo clic
derecho → Nueva carpeta → escribe `libros`.

**Paso 2.** Copia todos los libros `.md` que quieres procesar dentro
de la carpeta `libros`. Tu carpeta debe verse así:

```
KB Extraction\
  ├── extract_kb.py
  ├── extraction_prompt.md
  └── libros\
        ├── Run Less Run Faster.md
        ├── Daniels Running Formula.md
        └── Hansons Marathon Method.md
```

**Paso 3.** Abre PowerShell en tu carpeta de trabajo (ver PASO 5).

**Paso 4.** Ejecuta este comando. Reemplaza `MODELO` con `opus` o `sonnet`:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input libros\ --output kb_out --mode batch --model MODELO
```

**Ejemplo:**

```powershell
python extract_kb.py --prompt extraction_prompt.md --input libros\ --output kb_out --mode batch --model opus
```

**Paso 5.** Presiona Enter. El script envía todos los libros en una
sola operación y muestra un resumen:

```
Preparando 3 libro(s) para el Batch API...

  Run Less Run Faster        ~162,000 tokens  ~$1.25
  Daniels Running Formula    ~148,000 tokens  ~$1.14
  Hansons Marathon Method    ~155,000 tokens  ~$1.19

  Costo estimado : ~$3.58 USD (50% desc. Batch API)
  Entrega        : máximo 24 horas

Enviando... enviado.

============================================================
  Batch ID  : msgbatch_01abc123xyz...
============================================================
```

**Paso 6.** Anota el Batch ID. Cubre todos los libros del envío.

**Paso 7.** Cuando hayan pasado unas horas, descarga todos los
resultados con el **CASO D**.

> Nota: con varios libros no se usa `--book-meta`. El script toma
> el nombre de cada archivo automáticamente.

---

## CASO D — Descargar resultados del batch

Usa esto después de enviar un batch (Caso B o C) para verificar si
está listo y descargarlo.

**Paso 1.** Abre PowerShell en tu carpeta de trabajo (ver PASO 5).

**Paso 2.** Ejecuta este comando. Reemplaza `msgbatch_01abc123xyz`
con tu Batch ID real:

```powershell
python extract_kb.py --check msgbatch_01abc123xyz --output kb_out
```

> ¿Dónde está tu Batch ID? Lo anotaste al enviar el batch.
> Si no lo tienes, ábrelo desde el Explorador de Windows:
> navega a `kb_out\` → abre el archivo `batch_pending.json` con
> Notepad → busca la línea que dice `"batch_id"`.

**Paso 3.** El script verifica el estado:

**Si aún no está listo:**

```
Consultando batch: msgbatch_01abc123xyz
Estado : in_progress

Aún no está listo. Vuelve a consultar con:
  python extract_kb.py --check msgbatch_01abc123xyz --output kb_out
```

Cierra PowerShell y vuelve a intentarlo más tarde.

**Si ya está listo:**

```
Consultando batch: msgbatch_01abc123xyz
Estado : ended

Batch listo. Descargando...
  ✓ Run Less Run Faster        out=48,203t  → run-less-run-faster_kb.md
  ✓ Daniels Running Formula    out=51,847t  → daniels-running-formula_kb.md

============================================================
  Descargados : 2  |  Errores : 0
  Guardados en: kb_out
============================================================
```

**Paso 4.** Los archivos KB están en tu carpeta `kb_out\`. Ábrelos
desde el Explorador de Windows haciendo doble clic.

---

## Referencia rápida

### Elegir entre Opus y Sonnet

| | Opus (default) | Sonnet |
|---|---|---|
| **Cómo activarlo** | No escribir nada | Agregar `--model sonnet` al final |
| **Calidad** | Máxima | Muy buena |
| **Costo immediate** | ~$2–3 / libro | ~$1.20–1.80 / libro |
| **Costo batch** | ~$1–1.50 / libro | ~$0.60–0.90 / libro |
| **Para qué libros** | Tablas densas, planes numéricos, zonas | Libros más narrativos |

Para libros de entrenamiento con muchas tablas y planes: **Opus**.

### Tabla de costos

| Modo | Modelo | Costo aprox. | Tiempo de espera |
|---|---|---|---|
| Inmediato | Opus | ~$2–3 | 2–5 minutos |
| Inmediato | Sonnet | ~$1.20–1.80 | 2–5 minutos |
| Batch | Opus | ~$1–1.50 | Máx. 24 horas |
| Batch | Sonnet | ~$0.60–0.90 | Máx. 24 horas |

---

## Solución de problemas

---

**`pip` o `python` no se reconocen**

Python no está en el PATH del sistema. Reinstálalo desde **python.org**
y durante la instalación marca la casilla **"Add Python to PATH"**.

---

**"Falta la API key" al correr el script**

La key no está configurada en esta sesión de PowerShell. Ejecuta:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Si hiciste el PASO 4B, cierra PowerShell y vuelve a abrirlo — la key
debería cargarse automáticamente.

---

**Error de ejecución de scripts deshabilitada**

```
No se puede cargar el archivo ...profile.ps1 porque la ejecución
de scripts está deshabilitada en este sistema.
```

Ejecuta este comando y escribe `S` cuando pregunte:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Luego cierra PowerShell y vuelve a abrirlo.

---

**"The system cannot find the path specified" al usar `notepad $PROFILE`**

El directorio del perfil no existe. Créalo primero con:

```powershell
New-Item -Path $PROFILE -Type File -Force
```

Luego vuelve a ejecutar `notepad $PROFILE`.

---

**El nombre del libro da error al ejecutar el comando**

Si el nombre del archivo tiene espacios, debe ir entre comillas:

```powershell
--input "Run Less Run Faster.md"
```

---

**El resultado dice `⚠ TRUNCADO`**

El KB generado es demasiado largo para el modo inmediato. Usa modo
batch que soporta hasta 200,000 tokens de output:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "libro.md" --output kb_out --mode batch --book-meta "Título | Autor | Edición"
```

---

**Quiero reprocesar un libro que ya procesé antes**

El script detecta que el archivo ya existe y no lo sobreescribe.
Agrega `--force` al final del comando para forzar el reprocesamiento:

```powershell
python extract_kb.py --prompt extraction_prompt.md --input "libro.md" --output kb_out --book-meta "Título | Autor | Edición" --force
```

---

**Perdí el Batch ID**

Está guardado automáticamente en `kb_out\batch_pending.json`.
Abre ese archivo con Notepad y busca la línea `"batch_id"`.

---

*Manual v2.2 — KB Extraction Pipeline*
