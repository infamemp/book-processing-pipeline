# Guía de Referencia Rápida

Para la guía completa y detallada, ve a [`HOW_TO_USE.md`](./HOW_TO_USE.md).
Esta es solo una hoja de referencia rápida para cuando ya conoces el proceso.

---

## ⚠️ REGLA #1 — TODOS los comandos se escriben desde la carpeta del repositorio

**Nunca** desde una carpeta de Google Drive (ni `_source_intake`, ni `Library`,
ni `combinados`). Esto aplica a los 3 pasos, siempre, sin excepción.

Antes de escribir CUALQUIER comando `.\stepX_...`:

1. Abre el explorador de Windows
2. Ve a la carpeta del repositorio:
   ```
   C:\Dev\Github\book-processing-pipeline
   ```
   o
   ```
   E:\Dev\github\book-processing-pipeline
   ```
3. Clic derecho dentro de ella (no dentro de ninguna subcarpeta) → **Abrir en Terminal**
4. Verifica que la terminal muestre esa misma ruta antes de escribir nada

Si tu terminal muestra una ruta que dice `..._source_intake`, `...Library...` o
`...combinados...`, **estás en el lugar equivocado** — los comandos van a fallar
con un error de "no se reconoce como nombre de un cmdlet". Cierra esa terminal y
repite los pasos 1-4.

---

## 1. Convertir un libro nuevo

**Paso A — En el explorador de Windows** (no en la terminal):
Copia el archivo a `00_Anthropic\_source_intake\`

**Paso B — En la terminal, ya parado en la carpeta del repositorio** (ver Regla #1):
```powershell
.\step1_convert.ps1 -BookName "nombre-libro" -SourceFile "Nombre Exacto.epub"
```

Resultado en: `Library\nombre-libro\01_converted\`

---

## 2. Extraer el KB

**En la terminal, parado en la carpeta del repositorio** (ver Regla #1):
```powershell
# Inmediato (resultado al instante, más caro)
.\step2_extract.ps1 -BookName "nombre-libro" -Mode immediate

# Batch (hasta 24h, 50% más barato)
.\step2_extract.ps1 -BookName "nombre-libro" -Mode batch

# Revisar un batch pendiente
.\step2_extract.ps1 -BookName "nombre-libro" -Check "msgbatch_xxxxx"
```

Resultado en: `Library\nombre-libro\02_kb\`

---

## 3. Combinar varios libros

**Paso A — En el explorador de Windows** (no en la terminal):
1. Copia los `.md` que quieras combinar a `combinados\_staging\`
2. Renómbralos con prefijo numérico para definir el orden: `01_`, `02_`, `03_`...

**Paso B — En la terminal, parado en la carpeta del repositorio** (ver Regla #1):
```powershell
.\step3_combine.ps1 -OutputName "nombre_final.md"
```

Resultado en: `combinados\nombre_final.md` (y `_staging` se vacía solo)

---

## Estructura de carpetas (Google Drive)

```
00_Anthropic\
├── _source_intake\          ← libros nuevos sin procesar
├── Library\
│   └── <nombre-libro>\
│       ├── 00_original\     ← .epub / .pdf
│       ├── 01_converted\    ← resultado del Paso 1
│       └── 02_kb\           ← resultado del Paso 2
└── combinados\
    ├── _staging\            ← archivos a combinar (con prefijo 01_/02_/03_)
    └── <archivo final>      ← resultado del Paso 3
```

---

## Errores más comunes

| Error | Solución |
|---|---|
| `File not found in _source_intake` | Revisa que el nombre del archivo coincida exactamente (mayúsculas, espacios, extensión) |
| `convert.py not found` / `extract.py not found` / `combine.py not found` | Asegúrate de abrir la terminal dentro de la carpeta del repositorio |
| `Could not find the '00_Anthropic' folder` | Google Drive no está sincronizado, ábrelo y espera |
| `No .md file found in 01_converted` | Falta correr el Paso 1 primero para ese libro |
| `Found more than one .md file` | Deja solo un archivo en esa carpeta, mueve o borra el resto |
| Menciona `GEMINI_API_KEY` o `ANTHROPIC_API_KEY` | Esa variable no está configurada — ver guía completa, sección de API keys |

---

## Recordatorio entre las 2 computadoras

Antes de trabajar → **Fetch origin + Pull** en GitHub Desktop
Después de trabajar → **Commit + Push** en GitHub Desktop
