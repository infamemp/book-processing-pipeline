# Guía de Referencia Rápida

Para la guía completa y detallada, ve a [`HOW_TO_USE.md`](./HOW_TO_USE.md).
Esta es solo una hoja de referencia rápida para cuando ya conoces el proceso.

---

## 0. Abrir la terminal correcta (siempre la misma)

Abre el explorador → ve a la carpeta del repositorio → clic derecho dentro de
ella → **Abrir en Terminal**

```
C:\Dev\Github\book-processing-pipeline
```
o
```
E:\Dev\github\book-processing-pipeline
```

---

## 1. Convertir un libro nuevo

1. Pon el archivo en `00_Anthropic\_source_intake\`
2. Corre:
   ```powershell
   .\step1_convert.ps1 -BookName "nombre-libro" -SourceFile "Nombre Exacto.epub"
   ```
3. Resultado en: `Library\nombre-libro\01_converted\`

---

## 2. Extraer el KB

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

1. Copia los `.md` que quieras combinar a `combinados\_staging\`
2. Renómbralos con prefijo numérico para definir el orden: `01_`, `02_`, `03_`...
3. Corre:
   ```powershell
   .\step3_combine.ps1 -OutputName "nombre_final.md"
   ```
4. Resultado en: `combinados\nombre_final.md` (y `_staging` se vacía solo)

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
