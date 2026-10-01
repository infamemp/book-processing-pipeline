# Book Processing Pipeline

Convierte libros (EPUB/PDF) en una base de conocimiento (KB) lista para que una IA la use sola:
Infame Elite Endurance Coach, el sistema de nutrición, Claude, Gemini o MCP.
Cada libro es independiente: no hay paso de "combinar".

```
Libro (.epub/.pdf)  →  convert.py  →  libro.md  →  extract.py  →  _core.md + _biblioteca.md
```

Este repo guarda **solo código**. Los libros y los KB (material con derechos de autor) no se suben a Git.

## La app (ventana)

La forma fácil: arrastras el libro, apruebas el costo con un botón y eliges la carpeta de salida.

- **Programa (.exe):** doble clic en `build.bat` (una vez por computadora y cada vez que actualices el repo). Crea `dist\BookPipeline.exe` y el acceso directo **Book Pipeline** en el Escritorio. No necesita Python para usarse. Acepta EPUB y PDF.
- **Desde el código:** `pythonw app\ventana.py` (acepta también DOCX).

- **Carpeta de salida:** botón *Cambiar…* (se recuerda). Por defecto, `Google Drive\00_Anthropic\Library`.
- **Modo:** *Lote* (más barato, tarda de minutos a horas) o *Inmediato*.
- Varios libros se procesan en fila, uno a la vez. Si cierras la app, *Reanudar* sigue donde iba sin volver a pagar.
- Piezas en `app/`: `ventana.py` (ventana), `servidor.py` (servidor local), `trabajos.py` (fila de libros), `config.py` (llaves y carpetas) y `web/index.html` (la página). Preparadas para correr también en un VPS (`BPP_MODO=servidor`).

`procesar_libro.ps1` sigue funcionando igual, y ambos usan la misma carpeta de resultados.

## Qué produce cada libro

| Archivo | Contenido |
|---|---|
| `<libro>_core.md` | Filosofía, modelo integral, mecanismos, glosario, todas las tablas, fórmulas, pruebas, metodología, reglas de decisión, precauciones, evidencia y notas de vigencia (marcadas como ajenas al libro). |
| `<libro>_biblioteca.md` | Planes, entrenamientos, ejercicios, recetas y formatos, tal como se publicaron. |
| `<libro>_indice.json` | Metadatos listos para `kb_indice.json`. |
| `<libro>_reporte.txt` | Cobertura, avisos de la verificación de números y costo. |

Dominios: `endurance-sport`, `strength-training`, `senior-health`, `nutrition` (con los 10 códigos de condición del sistema clínico), `general`.

## Cómo funciona

1. **convert.py**: EPUB/PDF → Markdown. Las imágenes y tablas de imagen se transcriben con Gemini (se guarda caché y un reporte de lo descartado).
2. **extract.py** (Claude Sonnet 5.5 + Gemini 3.8 Flash):
   - MAP: metadatos, dominio, nivel de autoridad y división en capítulos.
   - EXTRACT: una llamada por capítulo.
   - VERIFY: Gemini compara lo extraído contra el texto; corrige, agrega lo que faltó y elimina lo inventado.
   - SYNTHESIS: panorama, Modelo Integral y notas de vigencia.
   - Revisión automática de números que no están en el capítulo.

Todo queda guardado en `_work_<libro>`. Si algo falla, al repetir el comando solo se hace lo que falta.

## Modos y costo

- **Inmediato** (por defecto): resultado en minutos.
- **Lote** (`-Lote`): ~50% más barato; tarda de minutos a horas (máximo 24 h). El programa espera solo hasta que termine; si se cierra la ventana, se repite el mismo comando y retoma.
- Antes de gastar, muestra el costo estimado y pide confirmación.
- Un libro de tamaño medio cuesta alrededor de $1.60 en lote y $3–4 en inmediato.

## Instalación (una sola vez por computadora)

```powershell
pip install -r requirements.txt
```

Variables de entorno de Windows (permanentes, nunca en el código): `BPP_ANTHROPIC_API_KEY` (llave de Claude exclusiva de esta app; si no existe se usa `ANTHROPIC_API_KEY`) y `GEMINI_API_KEY`.
Necesitas saldo en la cuenta de Anthropic.

## Dónde quedan los archivos

`Google Drive\00_Anthropic\Library\<libro>\` (se detecta solo). Si no encuentra Google Drive, usa una carpeta `kb_<libro>` junto al libro.

## Dos computadoras

Antes de trabajar: Fetch origin + Pull en GitHub Desktop. Después: Commit + Push.

Guía paso a paso: [`GUIA_RAPIDA.md`](./GUIA_RAPIDA.md). Las instrucciones de extracción viven en [`extraction_prompts.md`](./extraction_prompts.md).
