# Book Processing Pipeline

Convierte libros (EPUB/PDF) en una base de conocimiento (KB) lista para que una IA la use sola:
Infame Elite Endurance Coach, el sistema de nutrición, Claude, Gemini o MCP.
Cada libro es independiente: no hay paso de "combinar".

```
Libro (.epub/.pdf)  →  convert.py  →  libro.md  →  extract.py  →  _core.md + _biblioteca.md
```

Este repo guarda **solo código**. Los libros y los KB (material con derechos de autor) no se suben a Git.

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
- **Lote** (`-Lote`): ~50% más barato; tarda de minutos a horas (máximo 24 h). Se repite el mismo comando hasta que termine.
- Antes de gastar, muestra el costo estimado y pide confirmación.
- Un libro de tamaño medio cuesta alrededor de $1.60 en lote y $3–4 en inmediato.

## Instalación (una sola vez por computadora)

```powershell
pip install -r requirements.txt
```

Variables de entorno de Windows (permanentes, nunca en el código): `ANTHROPIC_API_KEY` y `GEMINI_API_KEY`.
Necesitas saldo en la cuenta de Anthropic.

## Dónde quedan los archivos

`Google Drive\00_Anthropic\Library\<libro>\` (se detecta solo). Si no encuentra Google Drive, usa una carpeta `kb_<libro>` junto al libro.

## Dos computadoras

Antes de trabajar: Fetch origin + Pull en GitHub Desktop. Después: Commit + Push.

Guía paso a paso: [`GUIA_RAPIDA.md`](./GUIA_RAPIDA.md). Las instrucciones de extracción viven en [`extraction_prompts.md`](./extraction_prompts.md).
