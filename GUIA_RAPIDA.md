# Guía rápida: de un libro a su base de conocimiento (KB)

Esta guía es para alguien que **no conoce el proyecto**. Sigue los pasos en orden. No necesitas saber programar.

**Qué hace:** toma un libro (.epub o .pdf) y produce dos archivos que una IA puede usar sola:
- `…_core.md`: el conocimiento completo (filosofía, tablas, fórmulas, pruebas, reglas, precauciones).
- `…_biblioteca.md`: los planes, entrenamientos, ejercicios y recetas tal como los publica el libro.

**Cuánto cuesta:** un libro de tamaño medio, unos **$2 USD** en total con el modo lote (conversión ≈ $0.10–0.30, extracción ≈ $1.60). El programa **siempre te muestra el costo y te pregunta antes de gastar**. Si respondes `n`, no se cobra nada.

**Cuánto tarda:** el modo lote (el barato) tarda de **unos minutos a unas horas** en total. El programa espera solo; no tienes que hacer nada salvo dejar la ventana abierta.

---

## PARTE A. Preparación (solo la primera vez en cada computadora)

### A1. Instalar Python
1. Entra a https://www.python.org/downloads/ y descarga Python para Windows.
2. Al instalar, **marca la casilla "Add python.exe to PATH"** antes de pulsar Install.
3. Comprueba: abre PowerShell y escribe `python --version`. Debe mostrar un número de versión.

### A2. Descargar el proyecto
1. Instala GitHub Desktop si no lo tienes.
2. Clona el repositorio `infamemp/book-processing-pipeline` (File → Clone repository).
3. Si ya lo tenías, haz **Fetch origin** y **Pull** para tener la última versión.
4. Anota la carpeta donde quedó. Ejemplo: `E:\Dev\github\book-processing-pipeline`.

### A3. Instalar las librerías
1. Abre PowerShell.
2. Ve a la carpeta del proyecto (cambia la ruta por la tuya):
   ```powershell
   cd E:\Dev\github\book-processing-pipeline
   ```
3. Instala:
   ```powershell
   pip install -r requirements.txt
   ```
   Puede tardar un par de minutos. Si ya estaba instalado, solo dirá "Requirement already satisfied".

### A4. Conseguir las dos claves (API keys)
El programa usa dos servicios de IA. Cada uno te da una clave, que es una contraseña larga.

| Servicio | Para qué | Dónde se crea | Saldo |
|---|---|---|---|
| **Anthropic (Claude)** | Extraer el conocimiento | https://console.anthropic.com → API Keys | Recarga **$10** en Billing → Add credit |
| **Google Gemini** | Leer imágenes/tablas y verificar | https://aistudio.google.com/apikey | Sigue lo que Google pida en pantalla |

Copia cada clave y guárdala en un lugar seguro. **Nunca la pegues en el proyecto ni en GitHub.**

### A5. Guardar las claves en Windows
En PowerShell (cambia `PEGA_AQUI…` por tus claves, conservando las comillas):
```powershell
setx ANTHROPIC_API_KEY "PEGA_AQUI_TU_CLAVE_DE_ANTHROPIC"
setx GEMINI_API_KEY "PEGA_AQUI_TU_CLAVE_DE_GEMINI"
```
Luego **cierra PowerShell y ábrelo de nuevo**. Sin este paso, no las reconoce.

Comprueba que quedaron (debe mostrar el inicio de la clave, no vacío):
```powershell
$env:ANTHROPIC_API_KEY.Substring(0,8)
$env:GEMINI_API_KEY.Substring(0,8)
```

### A6. Google Drive (opcional pero recomendado)
Si tienes Google Drive instalado y existe la carpeta `00_Anthropic\Library`, los resultados se guardan ahí automáticamente. Si no, se guardan en una carpeta `kb_<libro>` junto al libro.

---

## PARTE B. Procesar un libro

Haz esto **cada vez que quieras un libro nuevo**.

### B1. Prepara
1. Deja el libro (.epub o .pdf) en una carpeta fácil, por ejemplo Descargas. Anota la ruta completa. Ejemplo: `E:\Descargas\mi-libro.epub`.
2. Abre PowerShell y ve a la carpeta del proyecto:
   ```powershell
   cd E:\Dev\github\book-processing-pipeline
   ```
   **Siempre hay que estar en esa carpeta.** Si no, sale el error "El término '.\procesar_libro.ps1' no se reconoce".

### B2. Lanza el proceso
Escribe este comando (cambia la ruta por la de tu libro, y deja las comillas):
```powershell
.\procesar_libro.ps1 -Libro "E:\Descargas\mi-libro.epub" -Lote
```
- `-Lote` = modo barato (la mitad del precio, tarda más).
- Sin `-Lote` = modo inmediato (resultado en minutos, cuesta el doble).

### B3. Responde a las preguntas de costo
El programa se detiene en cada pasada que cuesta dinero y muestra algo así:
```
Costo estimado: ~$0.29 USD
¿Continuar? [s/N]:
```
- Escribe `s` y Enter para continuar.
- Escribe `n` (o solo Enter) para cancelar sin gastar nada.

Lo normal es que cada pasada pida menos de $1.00. Si alguna pide mucho más, cancela y revisa antes.

### B4. Conversión (primera pasada)
Verás "Convirtiendo el libro a Markdown…" y un costo pequeño por transcribir las imágenes con Gemini (≈ $0.10–0.30 en un libro con unas 50 imágenes). Al terminar aparece un recuadro con "Todo el contenido quedó transcrito".
- Esto se hace **una sola vez por libro**. Si repites el comando, no se vuelve a cobrar.
- Un PDF escaneado cuesta más, porque cada página se lee con IA.

### B5. Extracción en modo lote: déjalo abierto
Las pasadas de la extracción se envían a Anthropic y **no terminan al instante** (minutos u horas). El programa **espera solo**: revisa cada 3 minutos y avanza a la siguiente pasada cuando la anterior termina. Verás mensajes como:
```
Lote extract en proceso — listos 3, procesando 11…
[14:05] Esperando a Anthropic... próxima revisión en 3 min.
```
Qué hacer:
1. **Responde `s` a las preguntas de costo** (son dos: la del MAP y una segunda que cubre EXTRACT + VERIFY + SYNTHESIS juntas).
2. **Deja la ventana de PowerShell abierta** y no apagues la computadora hasta que termine.
3. **Si cierras la ventana o se apaga la PC:** no pasa nada. Abre PowerShell, haz `cd` a la carpeta y corre **el mismo comando de B2**. Retoma donde iba y no repite nada pagado.

Las pasadas son: **MAP** (leer el libro y dividirlo en capítulos) → **EXTRACT** (sacar el conocimiento de cada capítulo) → **VERIFY** (Gemini revisa y corrige) → **SYNTHESIS** (resumen e integración).

### B6. Saber que terminó
Termina cuando aparece un bloque como este:
```
CORE       : …\libro_core.md
BIBLIOTECA : …\libro_biblioteca.md
Reporte    : …\libro_reporte.txt
Entradas   : 120  (VERIFY corrigió 5, agregó 9, eliminó 0)
Avisos     : 1   Costo acumulado: $1.90 USD
```
Si en vez de eso dice **KB PARCIAL**, fue una prueba con pocos capítulos (ver Parte D), no el libro completo.

---

## PARTE C. Revisar y usar el resultado

### C1. Dónde están los archivos
En `Google Drive\00_Anthropic\Library\<nombre-del-libro>\` (o en `kb_<libro>` junto al libro, si no hay Drive):

| Archivo | Para qué sirve | ¿Se usa? |
|---|---|---|
| `…_core.md` | Conocimiento completo | **Sí** |
| `…_biblioteca.md` | Planes, entrenamientos, recetas | **Sí** |
| `…_indice.json` | Datos del libro para el sistema de nutrición | Sí, si aplica |
| `…_reporte.txt` | Informe de calidad y costos | Para revisar |
| `libro.md` | El libro convertido | Guárdalo |
| `_work_libro\` | Carpeta de trabajo interna | **No la borres hasta terminar**; después ya no hace falta |

### C2. Revisión rápida (5 minutos)
1. Abre `…_reporte.txt` y mira la sección **AVISOS**. Son números del KB que no se encontraron en el capítulo del libro. Casi siempre son valores derivados (por ejemplo, un año calculado), pero revisa cada uno contra el libro.
2. Abre `…_core.md` y comprueba una tabla importante del libro: que tenga todas las filas y columnas.
3. Si algo está mal, avisa antes de usar el KB.

---

## PARTE D. Prueba barata (opcional)

Para probar con solo dos capítulos y gastar centavos, añade `-Unidades`:
```powershell
.\procesar_libro.ps1 -Libro "E:\Descargas\mi-libro.epub" -Lote -Unidades "U05,U08"
```
Sale un KB **parcial** (sin la síntesis final). No sirve como KB definitivo.

---

## PARTE E. Problemas comunes

| Qué ves | Qué significa | Qué hacer |
|---|---|---|
| `El término '.\procesar_libro.ps1' no se reconoce` | Estás en otra carpeta | `cd` a la carpeta del proyecto y repite |
| `Falta la variable de entorno ANTHROPIC_API_KEY` (o GEMINI) | No se guardó la clave | Repite el paso A5 y abre PowerShell de nuevo |
| `Your credit balance is too low` | Se acabó el saldo de Anthropic | Recarga en console.anthropic.com → Billing y repite el mismo comando (no repite lo ya pagado) |
| `No encuentro el libro` | La ruta está mal escrita | Copia la ruta completa del archivo y ponla entre comillas |
| `… no está firmado digitalmente` / script bloqueado | Windows bloquea scripts | Una sola vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y repite |
| Dice "Esperando a Anthropic…" | Normal: el lote no ha terminado | Déjalo abierto; revisa solo cada 3 minutos |
| Se detuvo o dio error a la mitad | Falla temporal | Repite el mismo comando: continúa desde donde quedó |
| Una línea larga sobre "automatic function calling" | Aviso de una librería | Es inofensivo, ignóralo |

Si algo no está en la tabla, copia el mensaje completo de PowerShell y pídele ayuda a Claude con él.

---

## Resumen de una línea

`cd` a la carpeta del proyecto → `.\procesar_libro.ps1 -Libro "ruta\libro.epub" -Lote` → responde `s` a los costos → deja la ventana abierta hasta que aparezca **CORE / BIBLIOTECA / Reporte** (si se cierra, repite el mismo comando).
