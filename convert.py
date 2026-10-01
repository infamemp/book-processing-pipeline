#!/usr/bin/env python3
"""
convert.py — Paso 1 del pipeline: libro (EPUB / PDF / otros) → Markdown limpio.

Versión 2.2

QUÉ HACE
  EPUB : lee el libro capítulo por capítulo en el orden real de lectura (spine).
         Cada imagen de contenido (tabla, gráfica, plan, página escaneada) se
         transcribe con Gemini y se inserta EN SU LUGAR dentro del capítulo.
         Si el EPUB trae números de página de la edición impresa, se conservan.
  PDF  : extrae el texto de cada página con PyMuPDF. Las imágenes de contenido
         de cada página se transcriben con Gemini y se insertan en esa misma
         página. Las páginas escaneadas (sin texto) se transcriben completas.
         Cada página queda marcada con <!-- PAGE N --> para poder citarla.
  Otros: DOCX, PPTX, HTML, etc. se convierten con MarkItDown (sin imágenes).

GARANTÍAS
  - Nada se pierde en silencio: si una imagen o página no se pudo transcribir,
    queda una marca visible [IMAGE NOT PROCESSED: ...] / [PAGE NOT PROCESSED: ...]
    y aparece en el reporte.
  - Reintentos automáticos (3) ante errores de la API.
  - Caché: las transcripciones exitosas se guardan en <salida>.ocr_cache.json.
    Si vuelves a correr la conversión, solo se procesa lo que faltó o falló
    (no se paga dos veces).
  - Antes de gastar, muestra el costo estimado y pide confirmación
    (usa --yes para omitir la pregunta).
  - Al terminar genera <salida>.conversion_report.txt con el detalle.

MODO VENTANA (app)
  Si la variable de entorno BPP_UI=1 está definida (la define la app), la
  pregunta de costo y el resumen final se envían como líneas "@@BPP {json}" y
  la respuesta ("s" o "n") se lee de la entrada estándar. Sin BPP_UI, todo
  funciona igual que en la consola.

REQUISITOS
  pip install --upgrade markitdown google-genai pymupdf markdownify beautifulsoup4 Pillow
  Variable de entorno GEMINI_API_KEY (para imágenes y páginas escaneadas).

USO
  python convert.py "libro.epub"
  python convert.py "libro.pdf" -o "salida.md"
  python convert.py "libro.pdf" --yes            (sin pregunta de confirmación)
  python convert.py "libro.pdf" --workers 6      (más imágenes en paralelo)
"""

import argparse
import hashlib
import io
import json
import os
import posixpath
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

CONVERTER_VERSION = "2.2"

# ── Modelo y precios ─────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-3.8-flash"

# USD por millón de tokens (input, output incluyendo razonamiento).
# Fuente: ai.google.dev/gemini-api/docs/pricing (sep 2026).
# Nota: Gemini 3.8 Flash sube a $1.50 / $7.50 a partir del 1 ene 2027.
PRICES = {
    "gemini-3.8-flash":      (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
}
# Estimado por imagen/página, solo para el aviso previo (~1.5k in, ~1k out).
EST_TOKENS_IN_PER_JOB = 1500
EST_TOKENS_OUT_PER_JOB = 1000

MAX_OUTPUT_TOKENS = 16384
RETRIES = 3
RETRY_WAITS = (3, 10, 30)
DEFAULT_WORKERS = 4

# ── Umbrales ─────────────────────────────────────────────────────────────────

PDF_SCANNED_MAX_CHARS = 100      # página con menos texto que esto = escaneada
PDF_FULLPAGE_IMAGE_RATIO = 0.85  # imagen que cubre ≥85% de la página = escaneo
PDF_MIN_IMAGE_PT = 72            # imágenes de menos de 1 pulgada = decorativas
PDF_MIN_IMAGE_AREA_RATIO = 0.02  # imágenes de menos de 2% de la página = decorativas
PDF_REPEATED_IMAGE_PAGES = 3     # imagen repetida en >3 páginas = logo/fondo
PDF_RENDER_ZOOM = 2.0            # 144 dpi para transcribir

IMG_MIN_PX = 100                 # imágenes EPUB más chicas = decorativas
IMG_MIN_BYTES = 3000
IMG_REPEATED_TIMES = 5           # imagen EPUB usada >5 veces = decorativa
IMG_MAX_PX = 4096                # se reduce si es más grande

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

# Archivos de EPUB que no aportan contenido (nombre exacto).
SKIP_SECTIONS = {
    "cover.html", "cover.xhtml", "halftitle.html", "halftitle.xhtml",
    "contents.html", "contents.xhtml", "toc.html", "toc.xhtml",
    "nav.html", "nav.xhtml", "reader.html", "reader.xhtml",
}

DECORATIVE_NAME_PATTERNS = (
    "cover", "title_page", "_logo", "logo_", "next-reads", "backad",
    "globalback", "ornament", "divider", "000_bar", "000_section",
)
DECORATIVE_ALT_KEYWORDS = ("ornament", "logo", "next reads", "next-reads", "decorative")

# ── Instrucciones para Gemini ────────────────────────────────────────────────

IMAGE_PROMPT = """\
You are transcribing ONE image taken from a book. The transcription will be used
to build a precise knowledge base, so fidelity matters more than style.

Output clean Markdown ONLY — no preamble, no comments, no code fences.

Rules:
- Use the same language as the text in the image. Never translate.
- Transcribe every piece of text exactly: numbers, units, symbols, footnotes.
- Tables (zones, paces, doses, nutrient values, lab ranges, schedules, plans):
  a Markdown table with every row, column and header. Keep empty cells empty.
- Weekly plans / calendars: keep the week × day grid as a Markdown table.
- Charts / graphs: state the chart type and title, each axis with its units,
  and every value that is explicitly labeled. Describe the visible trend.
  NEVER estimate values that are not labeled.
- Diagrams / flowcharts: describe the structure, the relationships and all labels.
- Exercise or technique photos: one line describing what is shown, plus any caption.
- Purely decorative images (ornaments, logos, chapter-opener or mood photos of
  athletes/scenery with no instructional or data content): output exactly
  [DECORATIVE] and nothing else.
- If part of the image is unreadable, write [ILLEGIBLE] in that spot. Never guess."""

FORCED_NOTE = """\
IMPORTANT: in the book this image sits next to a caption such as "Table 6.3" or
"Figure 2.1", so it very likely contains data. Do NOT answer [DECORATIVE].
Transcribe it following the rules above. Only if it is truly a photo with no
data at all, describe what it shows in one line.

"""

# Leyendas que indican que una imagen es una tabla/figura del libro
CAPTION_RE = re.compile(
    r"\b(Table|Figure|Fig\.|Chart|Exhibit|Diagram|Tabla|Figura|Cuadro|Gr[aá]fic[ao]|Esquema)"
    r"\s*\d+(?:[.\-]\d+)?", re.IGNORECASE)
CAPTION_WINDOW = 500   # caracteres antes/después de la imagen donde se busca la leyenda

PAGE_PROMPT = """\
You are transcribing ONE full page of a book (a scan or a page image). The
transcription will be used to build a precise knowledge base, so fidelity
matters more than style.

Output clean Markdown ONLY — no preamble, no comments, no code fences.

Rules:
- Use the same language as the page. Never translate.
- Transcribe ALL body text in reading order, exactly as written.
- Headings → Markdown headings (#, ##, ###). Lists → Markdown lists.
- Skip running headers, running footers and the page number.
- Tables: a Markdown table with every row, column and header.
- Charts / figures on the page: describe them (type, title, axes with units,
  every labeled value) at the point where they appear. Never estimate values.
- Sidebars / boxes: transcribe them after the main text, preceded by "> ".
- If part of the page is unreadable, write [ILLEGIBLE] in that spot. Never guess."""


# ═════════════════════════════════════════════════════════════════════════════
# Estructuras de trabajo
# ═════════════════════════════════════════════════════════════════════════════

# ── Modo ventana (app) ──────────────────────────────────────────────────────
# La app define BPP_UI=1. Entonces cada pregunta o aviso sale como una línea
# "@@BPP {json}" y la respuesta llega por la entrada estándar.
UI_MODE = os.environ.get("BPP_UI") == "1"
UI_PREFIX = "@@BPP "

if UI_MODE:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass


def ui_event(evento, **datos):
    """Aviso para la app (no hace nada en la consola)."""
    if UI_MODE:
        print(UI_PREFIX + json.dumps({"evento": evento, **datos}, ensure_ascii=False), flush=True)


def ask_yes(lineas, costo=None):
    """¿Continuar? en la consola o en la ventana de la app. Devuelve True/False."""
    if UI_MODE:
        ui_event("confirmar", programa="convert", lineas=lineas, costo=costo)
        resp = sys.stdin.readline()
    else:
        try:
            resp = input("¿Continuar? [s/N]: ")
        except EOFError:
            print("Sin respuesta. Usa --yes para correr sin pregunta.")
            return False
    return resp.strip().lower() in ("s", "si", "sí", "y", "yes")


class Job:
    """Una imagen o página que Gemini debe transcribir."""

    def __init__(self, image_bytes, mime, label, kind, fallback_text=""):
        self.image_bytes = image_bytes
        self.mime = mime
        self.label = label            # ej. "p. 12, imagen 2" o "OEBPS/images/fig3.jpg"
        self.kind = kind              # "image" | "page"
        self.fallback_text = fallback_text  # texto nativo del PDF si la transcripción falla
        self.key = hashlib.sha1(image_bytes + kind.encode()).hexdigest()
        self.token = f"ZZOCRZZ{self.key[:16]}ZZ"
        self.rule_reason = ""         # motivo si las reglas la consideran decorativa
        self.captioned = False        # tiene una leyenda "Tabla/Figura N" cerca
        # resultado
        self.status = None            # ok | cached | decorative | truncated | recitation | blocked | failed | skipped
        self.text = ""
        self.reason = ""


class Report:
    def __init__(self, source, out_path, model):
        self.source = source
        self.out_path = out_path
        self.model = model
        self.kind = ""
        self.lines = []               # detalles de estructura
        self.problems = []            # (ubicación, motivo)
        self.discarded = []           # (ubicación, motivo) imágenes descartadas
        self.counts = {}
        self.tokens_in = 0
        self.tokens_out = 0
        self.started = time.time()

    def inc(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def cost(self):
        pin, pout = PRICES.get(self.model, PRICES[DEFAULT_MODEL])
        return (self.tokens_in * pin + self.tokens_out * pout) / 1_000_000

    def write(self, final_chars):
        c = self.counts
        L = []
        L.append("REPORTE DE CONVERSIÓN")
        L.append("=" * 60)
        L.append(f"Fuente          : {self.source}")
        L.append(f"Salida          : {self.out_path}")
        L.append(f"Tipo            : {self.kind}")
        L.append(f"Modelo imágenes : {self.model}")
        L.append(f"Fecha           : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        L.append(f"Duración        : {time.time() - self.started:.0f} s")
        L.append(f"Caracteres      : {final_chars:,}")
        L.append("")
        L.extend(self.lines)
        L.append("")
        L.append("TRANSCRIPCIONES CON GEMINI")
        L.append("-" * 60)
        for label, key in [
            ("Imágenes/páginas enviadas", "jobs_total"),
            ("  transcritas ahora", "ok"),
            ("  tomadas de caché (sin costo)", "cached"),
            ("  descartadas por decorativas (IA)", "decorative"),
            ("  re-transcritas por tener leyenda de tabla/figura", "forced"),
            ("  truncadas", "truncated"),
            ("  bloqueadas por derechos de autor", "recitation"),
            ("  bloqueadas por seguridad", "blocked"),
            ("  fallidas tras reintentos", "failed"),
            ("  sin procesar (sin API key)", "skipped"),
            ("Imágenes decorativas descartadas (reglas)", "decorative_rules"),
        ]:
            L.append(f"{label:<44}: {c.get(key, 0)}")
        L.append(f"{'Tokens (entrada / salida)':<44}: {self.tokens_in:,} / {self.tokens_out:,}")
        L.append(f"{'Costo real aproximado':<44}: ${self.cost():.3f} USD")
        L.append("")
        if self.problems:
            L.append(f"PROBLEMAS ({len(self.problems)}) — revisar")
            L.append("-" * 60)
            for loc, why in self.problems:
                L.append(f"  - {loc}: {why}")
            L.append("")
            L.append("Para reintentar solo lo que falló, vuelve a correr la misma")
            L.append("conversión: lo que ya salió bien se toma de la caché.")
        else:
            L.append("Sin problemas: todo el contenido quedó transcrito.")
        if self.discarded:
            L.append("")
            L.append(f"IMÁGENES DESCARTADAS COMO DECORATIVAS ({len(self.discarded)}) — para auditoría")
            L.append("-" * 60)
            for loc, why in self.discarded:
                L.append(f"  - {loc}: {why}")
        report_path = Path(self.out_path).with_suffix(".conversion_report.txt")
        report_path.write_text("\n".join(L) + "\n", encoding="utf-8")
        return report_path


# ═════════════════════════════════════════════════════════════════════════════
# Utilidades de imagen
# ═════════════════════════════════════════════════════════════════════════════

def image_info(image_bytes):
    """Devuelve (ancho, alto, formato) o (0, 0, None) si no se puede leer."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.size[0], img.size[1], (img.format or "").upper()
    except Exception:
        return 0, 0, None


def prepare_image(image_bytes):
    """
    Deja la imagen lista para Gemini: JPEG o PNG, máximo IMG_MAX_PX por lado.
    Devuelve (bytes, mime).
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        fmt = (img.format or "").upper()
        w, h = img.size
        needs_resize = max(w, h) > IMG_MAX_PX
        if fmt in ("JPEG", "PNG") and not needs_resize:
            return image_bytes, "image/jpeg" if fmt == "JPEG" else "image/png"
        if needs_resize:
            scale = IMG_MAX_PX / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        sys.exit("ERROR: falta Pillow. Instala con:  pip install Pillow")
    except Exception:
        return image_bytes, "image/jpeg"


def is_decorative_name(fname, alt):
    f = fname.lower()
    a = (alt or "").lower()
    if any(p in f for p in DECORATIVE_NAME_PATTERNS):
        return True
    if any(k in a for k in DECORATIVE_ALT_KEYWORDS):
        return True
    return False


# ═════════════════════════════════════════════════════════════════════════════
# Gemini
# ═════════════════════════════════════════════════════════════════════════════

class GeminiOCR:
    def __init__(self, model, cache_path, workers, report):
        self.model = model
        self.cache_path = Path(cache_path)
        self.workers = workers
        self.report = report
        self.client = None
        self.lock = threading.Lock()
        self.cache = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("AVISO: no existe GEMINI_API_KEY — las imágenes y páginas escaneadas")
            print("       quedarán marcadas como no procesadas.")
            print("       Ver README: Instalación (variable permanente de Windows).")
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            print("AVISO: falta google-genai. Instala con:  pip install --upgrade google-genai")

    # ── caché ──
    def _save_cache(self):
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path)

    # ── una llamada ──
    def _config(self):
        from google.genai import types
        kwargs = dict(
            max_output_tokens=MAX_OUTPUT_TOKENS,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        )
        if self.model.startswith("gemini-3"):
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        return types.GenerateContentConfig(**kwargs)

    def _call(self, job):
        from google.genai import types
        if job.kind == "page":
            prompt = PAGE_PROMPT
        elif job.kind == "image_forced":
            prompt = FORCED_NOTE + IMAGE_PROMPT
        else:
            prompt = IMAGE_PROMPT
        part = types.Part.from_bytes(data=job.image_bytes, mime_type=job.mime)
        last_error = ""
        for attempt in range(RETRIES):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=[part, prompt], config=self._config()
                )
                um = getattr(resp, "usage_metadata", None)
                if um:
                    with self.lock:
                        self.report.tokens_in += um.prompt_token_count or 0
                        self.report.tokens_out += (um.candidates_token_count or 0) + (
                            getattr(um, "thoughts_token_count", 0) or 0)
                cand = resp.candidates[0] if resp.candidates else None
                finish = str(getattr(cand, "finish_reason", "") or "")
                text = ""
                try:
                    text = (resp.text or "").strip()
                except Exception:
                    text = ""
                if "RECITATION" in finish:
                    return "recitation", text, "Gemini bloqueó la transcripción (derechos de autor)"
                if any(k in finish for k in ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII")):
                    return "blocked", text, f"bloqueada por filtro ({finish})"
                if "MAX_TOKENS" in finish:
                    return "truncated", text, "respuesta cortada por longitud"
                if text:
                    return "ok", text, ""
                last_error = f"respuesta vacía ({finish or 'sin motivo'})"
            except Exception as e:
                last_error = str(e)[:200]
            if attempt < RETRIES - 1:
                time.sleep(RETRY_WAITS[attempt])
        return "failed", "", last_error

    # ── lote ──
    def pending(self, jobs):
        return [j for j in unique_jobs(jobs) if j.key not in self.cache]

    def run(self, jobs):
        """Procesa todos los trabajos (en paralelo). Llena job.status/text/reason."""
        uniq = unique_jobs(jobs)
        todo = []
        for j in uniq:
            if j.key in self.cache:
                j.status, j.text = "cached", self.cache[j.key]
            elif self.client is None:
                j.status, j.reason = "skipped", "sin GEMINI_API_KEY"
            else:
                todo.append(j)

        if todo:
            print(f"\nTranscribiendo {len(todo)} imagen(es)/página(s) con {self.model} "
                  f"({self.workers} en paralelo)...")
            done = 0
            with ThreadPoolExecutor(max_workers=self.workers) as ex:
                futures = {ex.submit(self._call, j): j for j in todo}
                for fut in as_completed(futures):
                    j = futures[fut]
                    j.status, j.text, j.reason = fut.result()
                    done += 1
                    mark = "✓" if j.status == "ok" else "✗"
                    print(f"  [{done}/{len(todo)}] {mark} {j.label}"
                          + (f"  — {j.reason}" if j.reason else ""))
                    if j.status == "ok" and not (j.kind == "image_forced" and j.text.strip() == "[DECORATIVE]"):
                        with self.lock:
                            self.cache[j.key] = j.text
                            if done % 10 == 0:
                                self._save_cache()
            self._save_cache()

        # los duplicados copian el resultado de su original
        by_key = {j.key: j for j in uniq}
        for j in jobs:
            src = by_key[j.key]
            j.status, j.text, j.reason = src.status, src.text, src.reason


def unique_jobs(jobs):
    seen, out = set(), []
    for j in jobs:
        if j.key not in seen:
            seen.add(j.key)
            out.append(j)
    return out


def render_job(job, report):
    """Convierte el resultado de un trabajo en el texto que va al Markdown."""
    text = (job.text or "").strip()
    if job.status in ("ok", "cached") and text == "[DECORATIVE]":
        report.inc("decorative")
        if job.captioned:
            report.problems.append((job.label, "tiene leyenda de tabla/figura pero la IA la marcó decorativa"))
            return f"\n\n[IMAGE MARKED DECORATIVE DESPITE CAPTION: {job.label}]\n\n"
        report.discarded.append((job.label, "IA: decorativa"))
        return ""
    report.inc(job.status)

    if job.status in ("ok", "cached"):
        if job.kind == "image":
            return f"\n\n<!-- IMAGE: {job.label} -->\n{text}\n<!-- /IMAGE -->\n\n"
        return f"\n\n{text}\n\n"

    report.problems.append((job.label, job.reason or job.status))

    if job.status == "truncated":
        tail = f"\n[TRANSCRIPTION TRUNCATED: {job.label}]"
        if job.kind == "image":
            return f"\n\n<!-- IMAGE: {job.label} -->\n{text}{tail}\n<!-- /IMAGE -->\n\n"
        return f"\n\n{text}{tail}\n\n"

    if job.kind == "page":
        if job.fallback_text.strip():
            return (f"\n\n<!-- {job.label}: transcripción con imagen falló "
                    f"({job.reason}); se usa el texto nativo del PDF -->\n\n"
                    f"{job.fallback_text.strip()}\n\n")
        return f"\n\n[PAGE NOT PROCESSED: {job.label} — {job.reason}]\n\n"
    return f"\n\n[IMAGE NOT PROCESSED: {job.label} — {job.reason}]\n\n"


def recheck_captioned(ocr, jobs, report):
    """
    Si la IA marcó como decorativa una imagen que tiene leyenda de tabla/figura,
    se vuelve a pedir la transcripción con una instrucción más firme.
    """
    targets = [j for j in unique_jobs(jobs)
               if j.captioned and j.status in ("ok", "cached") and (j.text or "").strip() == "[DECORATIVE]"]
    if not targets:
        return
    print(f"\nRevisando {len(targets)} imagen(es) con leyenda de tabla/figura que la IA marcó decorativas...")
    forced = [Job(j.image_bytes, j.mime, j.label, "image_forced") for j in targets]
    ocr.run(forced)
    result = {}
    for j, f in zip(targets, forced):
        report.inc("forced")
        result[j.key] = (f.status, f.text, f.reason)
    for j in jobs:
        if j.key in result:
            j.status, j.text, j.reason = result[j.key]


def confirm_cost(ocr, jobs, model, assume_yes):
    """Muestra el costo estimado y pide confirmación. Devuelve False si se cancela."""
    pending = ocr.pending(jobs)
    cached = len(unique_jobs(jobs)) - len(pending)
    if not pending:
        if cached:
            print(f"\nTodas las transcripciones ({cached}) ya están en caché — costo $0.")
        return True
    if ocr.client is None:
        return True
    pin, pout = PRICES.get(model, PRICES[DEFAULT_MODEL])
    est = len(pending) * (EST_TOKENS_IN_PER_JOB * pin + EST_TOKENS_OUT_PER_JOB * pout) / 1_000_000
    pages = sum(1 for j in pending if j.kind == "page")
    images = len(pending) - pages
    lines = [f"Conversión — por transcribir con Gemini: {images} imagen(es) + {pages} página(s) completa(s)"]
    if cached:
        lines.append(f"Ya en caché (sin costo): {cached}")
    lines.append(f"Costo estimado: ~${est:.2f} USD  ({model})")
    print("\n" + "-" * 60)
    for ln in lines:
        print("  " + ln)
    print("-" * 60)
    if assume_yes:
        return True
    return ask_yes(lines, round(est, 2))


# ═════════════════════════════════════════════════════════════════════════════
# EPUB
# ═════════════════════════════════════════════════════════════════════════════

OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
CONT_NS = "urn:oasis:names:tc:opendocument:xmlns:container"


def zip_resolver(zf):
    names = {n.lower(): n for n in zf.namelist()}

    def resolve(base_dir, href):
        href = unquote(href.split("#")[0].split("?")[0]).replace("\\", "/")
        if not href:
            return None
        full = posixpath.normpath(posixpath.join(base_dir, href)) if base_dir else posixpath.normpath(href)
        return names.get(full.lower())
    return resolve


def read_opf(zf):
    """Devuelve (opf_dir, manifest, spine, metadata)."""
    opf_path = None
    try:
        root = ET.fromstring(zf.read("META-INF/container.xml"))
        rf = root.find(f".//{{{CONT_NS}}}rootfile")
        opf_path = rf.get("full-path") if rf is not None else None
    except Exception:
        pass
    if not opf_path:
        opf_path = next((n for n in zf.namelist() if n.lower().endswith(".opf")), None)
    if not opf_path:
        raise ValueError("EPUB sin archivo OPF (estructura dañada)")

    opf = ET.fromstring(zf.read(opf_path))
    opf_dir = posixpath.dirname(opf_path)

    manifest = {}
    for item in opf.iter(f"{{{OPF_NS}}}item"):
        manifest[item.get("id")] = {
            "href": item.get("href", ""),
            "type": item.get("media-type", ""),
            "props": item.get("properties", "") or "",
        }
    spine = [ir.get("idref") for ir in opf.iter(f"{{{OPF_NS}}}itemref")]

    meta = {}
    md = opf.find(f"{{{OPF_NS}}}metadata")
    if md is not None:
        def all_of(tag):
            return [e.text.strip() for e in md.findall(f"{{{DC_NS}}}{tag}") if e.text and e.text.strip()]
        for tag, key in [("title", "title"), ("creator", "authors"), ("date", "date"),
                         ("publisher", "publisher"), ("language", "language"),
                         ("identifier", "identifier")]:
            vals = all_of(tag)
            if vals:
                meta[key] = vals if key == "authors" else vals[0]
    return opf_dir, manifest, spine, meta


def html_to_markdown(html_text, html_dir, resolve, zf, report, jobs, img_uses):
    """Convierte un capítulo XHTML a Markdown, dejando marcadores para las imágenes."""
    from bs4 import BeautifulSoup, NavigableString
    from markdownify import markdownify

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "head", "title"]):
        tag.decompose()

    # Números de página de la edición impresa
    for el in soup.find_all(True):
        et = (el.get("epub:type") or "") + " " + (el.get("role") or "")
        if "pagebreak" in et:
            num = el.get("title") or el.get("aria-label") or el.get_text(strip=True) or ""
            if not num:
                m = re.search(r"(\d+)$", el.get("id", "") or "")
                num = m.group(1) if m else ""
            num = re.sub(r"[^\w\-]", "", num)
            el.replace_with(NavigableString(f"\n\nZZPAGEZZ{num}ZZ\n\n") if num else NavigableString(""))

    # Enlaces internos: solo el texto visible
    for a in soup.find_all("a"):
        href = a.get("href", "") or ""
        if not href.startswith(("http://", "https://", "mailto:")):
            a.unwrap()

    # Imágenes (<img> y <image> dentro de SVG)
    for img in soup.find_all(["img", "image"]):
        src = img.get("src") or img.get("xlink:href") or img.get("href") or ""
        alt = img.get("alt", "") or ""
        entry = resolve(html_dir, src) if src else None
        if not entry or Path(entry).suffix.lower() not in IMAGE_EXTENSIONS:
            img.replace_with(NavigableString(""))
            continue
        fname = Path(entry).name
        data = zf.read(entry)
        w, h, _ = image_info(data)
        rule = ""
        if is_decorative_name(fname, alt):
            rule = "reglas: nombre/alt de adorno"
        elif len(data) < IMG_MIN_BYTES or (w and h and (w < IMG_MIN_PX or h < IMG_MIN_PX)):
            rule = f"reglas: muy pequeña ({w}x{h}px, {len(data):,} bytes)"
        prepared, mime = prepare_image(data)
        job = Job(prepared, mime, entry, "image")
        job.rule_reason = rule
        jobs.append(job)
        img_uses[job.key] = img_uses.get(job.key, 0) + 1
        img.replace_with(NavigableString(f"\n\n{job.token}\n\n"))

    body = soup.body or soup
    md = markdownify(str(body), heading_style="ATX", bullets="-", strip=["span", "div"],
                    escape_underscores=False, escape_asterisks=False)
    return md


def convert_epub(path, ocr, report, assume_yes):
    report.kind = "EPUB"
    jobs, sections, img_uses = [], [], {}
    with zipfile.ZipFile(path) as zf:
        resolve = zip_resolver(zf)
        opf_dir, manifest, spine, meta = read_opf(zf)
        skipped = 0
        for idref in spine:
            item = manifest.get(idref)
            if not item:
                continue
            entry = resolve(opf_dir, item["href"])
            if not entry:
                continue
            name = Path(entry).name.lower()

            if item["type"].startswith("image/"):
                prepared, mime = prepare_image(zf.read(entry))
                job = Job(prepared, mime, entry, "page")
                jobs.append(job)
                sections.append((entry, job.token))
                continue

            if "html" not in item["type"]:
                continue
            if "nav" in item["props"].split() or name in SKIP_SECTIONS:
                skipped += 1
                continue

            html_text = zf.read(entry).decode("utf-8", errors="replace")
            md = html_to_markdown(html_text, posixpath.dirname(entry), resolve, zf, report, jobs, img_uses)
            if md.strip():
                sections.append((entry, md))

        report.lines.append(f"Secciones (capítulos/archivos) : {len(sections)}")
        report.lines.append(f"Secciones omitidas (índice/nav/portada) : {skipped}")

    # ¿Qué imágenes tienen una leyenda "Tabla/Figura N" cerca?
    captioned_tokens = set()
    for _, md in sections:
        for m in re.finditer(r"ZZOCRZZ[0-9a-f]{16}ZZ", md):
            ctx = md[max(0, m.start() - CAPTION_WINDOW): m.end() + CAPTION_WINDOW]
            ctx = re.sub(r"ZZOCRZZ[0-9a-f]{16}ZZ", " ", ctx)
            if CAPTION_RE.search(ctx):
                captioned_tokens.add(m.group(0))
    for j in jobs:
        j.captioned = j.token in captioned_tokens

    # Descartes por reglas (nunca si tiene leyenda de tabla/figura)
    repeated = {k for k, n in img_uses.items() if n > IMG_REPEATED_TIMES}
    drop_tokens, jobs_final = set(), []
    for j in unique_jobs(jobs):
        reason = ""
        if j.key in repeated and not j.captioned:
            reason = f"reglas: repetida {img_uses[j.key]} veces (viñeta/separador)"
        elif j.rule_reason and not j.captioned:
            reason = j.rule_reason
        if reason:
            drop_tokens.add(j.token)
            report.inc("decorative_rules")
            report.discarded.append((j.label, reason))
    jobs_final = [j for j in jobs if j.token not in drop_tokens]

    if not confirm_cost(ocr, jobs_final, ocr.model, assume_yes):
        sys.exit("Cancelado. No se escribió nada.")
    ocr.run(jobs_final)
    recheck_captioned(ocr, jobs_final, report)

    rendered = {t: "" for t in drop_tokens}
    for j in jobs_final:
        if j.token not in rendered:
            rendered[j.token] = render_job(j, report)

    parts = []
    for entry, md in sections:
        md = re.sub(r"ZZOCRZZ[0-9a-f]{16}ZZ", lambda m: rendered.get(m.group(0), ""), md)
        md = re.sub(r"ZZPAGEZZ([\w\-]+)ZZ", r"<!-- PAGE \1 -->", md)
        parts.append(f"<!-- SECTION: {entry} -->\n\n{md.strip()}")

    report.inc("jobs_total", len(unique_jobs(jobs_final)))
    return meta, "\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# PDF
# ═════════════════════════════════════════════════════════════════════════════

def _body_font_size(doc):
    """Tamaño de letra más común del libro (el del texto normal)."""
    sizes = {}
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    k = round(sp["size"], 1)
                    sizes[k] = sizes.get(k, 0) + len(sp["text"].strip())
    return max(sizes, key=sizes.get) if sizes else 10.0


def _join_lines(lines):
    """Une líneas conservando saltos; repara palabras cortadas con guion."""
    out = []
    for ln in lines:
        if out and out[-1].endswith("-") and ln[:1].islower():
            out[-1] = out[-1][:-1] + ln
        else:
            out.append(ln)
    return "\n".join(out)


def pdf_page_markdown(page, body_size):
    """
    Texto de una página conservando cada línea (importante para tablas sin
    bordes y listas de cifras), títulos detectados por tamaño de letra, y
    tablas con bordes convertidas a tablas Markdown.
    """
    tables = []
    try:
        for t in page.find_tables().tables:
            md = t.to_markdown().strip()
            if md:
                tables.append((t.bbox, md))
    except Exception:
        pass

    def in_table(bbox):
        x0, y0, x1, y1 = bbox
        for (tx0, ty0, tx1, ty1), _ in tables:
            ix = max(0, min(x1, tx1) - max(x0, tx0))
            iy = max(0, min(y1, ty1) - max(y0, ty0))
            area = max((x1 - x0) * (y1 - y0), 1)
            if ix * iy / area > 0.5:
                return True
        return False

    items = []
    for b in page.get_text("dict", sort=True)["blocks"]:
        if b.get("type") != 0 or in_table(b["bbox"]):
            continue
        lines, size, bold = [], 0, True
        for line in b["lines"]:
            txt = "".join(sp["text"] for sp in line["spans"]).strip()
            if not txt:
                continue
            lines.append(txt)
            for sp in line["spans"]:
                if sp["text"].strip():
                    size = max(size, sp["size"])
                    bold = bold and bool(sp["flags"] & 16)
        if not lines:
            continue
        text = _join_lines(lines)
        short = len(text) < 150
        if short and size >= body_size * 1.35:
            text = "# " + text.replace("\n", " ")
        elif short and (size >= body_size * 1.15 or (bold and len(lines) == 1 and len(text) < 90)):
            text = "## " + text.replace("\n", " ")
        items.append((b["bbox"][1], text))

    # insertar cada tabla antes del primer bloque que empieza debajo de ella
    for (bx0, by0, bx1, by1), md in tables:
        pos = next((i for i, (y, _) in enumerate(items) if y > by0), len(items))
        items.insert(pos, (by0, md))
    return "\n\n".join(t for _, t in items)


def pdf_native_pages(doc):
    """Texto de cada página. Devuelve (lista_de_textos, cantidad_de_tablas_con_bordes)."""
    body = _body_font_size(doc)
    texts = [pdf_page_markdown(p, body) for p in doc]
    ntables = sum(t.count("\n|") and 1 or 0 for t in texts)
    return texts, ntables


def convert_pdf(path, ocr, report, assume_yes):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # versiones antiguas
    report.kind = "PDF"
    doc = pymupdf.open(path)
    total = len(doc)
    print(f"  Páginas: {total}. Extrayendo texto...")
    native, table_pages = pdf_native_pages(doc)

    # ¿En cuántas páginas aparece cada imagen? (logos/fondos repetidos)
    xref_pages = {}
    for p in doc:
        for img in p.get_images(full=True):
            xref_pages.setdefault(img[0], set()).add(p.number)

    jobs, pages_out, scanned = [], [], 0
    zoom = pymupdf.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM)

    for page in doc:
        n = page.number + 1
        text = native[page.number]
        plain_len = len(page.get_text("text").strip())
        parea = abs(page.rect.width * page.rect.height) or 1
        infos = page.get_image_info(xrefs=True)

        full_img = any(
            abs(pymupdf.Rect(i["bbox"]).get_area()) >= PDF_FULLPAGE_IMAGE_RATIO * parea
            and len(xref_pages.get(i.get("xref", 0), ())) <= PDF_REPEATED_IMAGE_PAGES
            for i in infos
        )

        if plain_len < PDF_SCANNED_MAX_CHARS or full_img:
            scanned += 1
            pix = page.get_pixmap(matrix=zoom)
            job = Job(pix.tobytes("jpeg"), "image/jpeg", f"p. {n}", "page", fallback_text=text)
            jobs.append(job)
            pages_out.append((n, job.token))
            continue

        tokens, k = [], 0
        page_captioned = bool(CAPTION_RE.search(text))
        for idx, info in enumerate(infos, 1):
            xref = info.get("xref", 0)
            r = pymupdf.Rect(info["bbox"]) & page.rect
            loc = f"p. {n}, imagen #{idx}"
            min_pt = PDF_MIN_IMAGE_PT / 2 if page_captioned else PDF_MIN_IMAGE_PT
            reason = ""
            if r.is_empty or r.width < min_pt or r.height < min_pt:
                reason = "reglas: muy pequeña"
            elif not page_captioned and r.get_area() < PDF_MIN_IMAGE_AREA_RATIO * parea:
                reason = "reglas: área muy pequeña"
            elif xref and len(xref_pages.get(xref, ())) > PDF_REPEATED_IMAGE_PAGES:
                reason = f"reglas: repetida en {len(xref_pages[xref])} páginas (logo/fondo)"
            if reason:
                report.inc("decorative_rules")
                if "repetida" not in reason or n == min(xref_pages.get(xref, {n})):
                    report.discarded.append((loc, reason))
                continue
            k += 1
            pix = page.get_pixmap(matrix=zoom, clip=r)
            job = Job(pix.tobytes("jpeg"), "image/jpeg", f"p. {n}, imagen {k}", "image")
            job.captioned = page_captioned
            jobs.append(job)
            tokens.append(job.token)
        pages_out.append((n, text.strip() + ("\n\n" + "\n\n".join(tokens) if tokens else "")))

    report.lines.append(f"Páginas                        : {total}")
    report.lines.append(f"Páginas escaneadas (completas) : {scanned}")
    report.lines.append(f"Páginas con tablas detectadas  : {table_pages}")

    meta = {}
    m = doc.metadata or {}
    if m.get("title"):
        meta["title"] = m["title"]
    if m.get("author"):
        meta["authors"] = [m["author"]]
    if m.get("creationDate"):
        d = re.match(r"D:(\d{4})", m["creationDate"])
        if d:
            meta["date"] = d.group(1)
    doc.close()

    if not confirm_cost(ocr, jobs, ocr.model, assume_yes):
        sys.exit("Cancelado. No se escribió nada.")
    ocr.run(jobs)
    recheck_captioned(ocr, jobs, report)

    rendered = {}
    for j in jobs:
        if j.token not in rendered:
            rendered[j.token] = render_job(j, report)
    report.inc("jobs_total", len(unique_jobs(jobs)))

    parts = []
    for n, body in pages_out:
        body = re.sub(r"ZZOCRZZ[0-9a-f]{16}ZZ", lambda mm: rendered.get(mm.group(0), ""), body)
        parts.append(f"<!-- PAGE {n} -->\n\n{body.strip()}")
    return meta, "\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# Otros formatos
# ═════════════════════════════════════════════════════════════════════════════

def convert_other(path, report):
    try:
        from markitdown import MarkItDown
    except ImportError:
        sys.exit("ERROR: falta MarkItDown. Instala con:  pip install markitdown")
    report.kind = Path(path).suffix.upper().lstrip(".") + " (MarkItDown, sin imágenes)"
    return {}, MarkItDown().convert(path).text_content


# ═════════════════════════════════════════════════════════════════════════════
# Principal
# ═════════════════════════════════════════════════════════════════════════════

def yaml_header(meta, source, model, report):
    def q(v):
        return json.dumps(v, ensure_ascii=False)
    lines = ["---"]
    if meta.get("title"):
        lines.append(f"title: {q(meta['title'])}")
    if meta.get("authors"):
        lines.append("authors: [" + ", ".join(q(a) for a in meta["authors"]) + "]")
    for k in ("date", "publisher", "language", "identifier"):
        if meta.get(k):
            lines.append(f"{k}: {q(meta[k])}")
    lines.append(f"source_file: {q(Path(source).name)}")
    lines.append(f"source_format: {q(report.kind)}")
    lines.append(f"converted: {q(datetime.now(timezone.utc).strftime('%Y-%m-%d'))}")
    lines.append(f"converter: {q('convert.py ' + CONVERTER_VERSION)}")
    lines.append(f"image_model: {q(model)}")
    lines.append(f"unprocessed_items: {len(report.problems)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def tidy(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def convert(input_path, output_path, model, workers, assume_yes):
    src = Path(input_path)
    if not src.exists():
        sys.exit(f"ERROR: no existe el archivo: '{input_path}'")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    report = Report(str(src), str(out), model)
    ext = src.suffix.lower()
    print(f"\nConvirtiendo: {src.name}")

    if ext in (".epub", ".pdf"):
        ocr = GeminiOCR(model, out.with_suffix(".ocr_cache.json"), workers, report)
        if ocr.client:
            print(f"Gemini activo — modelo: {model}")
        meta, body = convert_epub(src, ocr, report, assume_yes) if ext == ".epub" \
            else convert_pdf(src, ocr, report, assume_yes)
    else:
        meta, body = convert_other(str(src), report)

    body = tidy(body)
    final = yaml_header(meta, src, model, report) + body
    out.write_text(final, encoding="utf-8")
    report_path = report.write(len(final))

    print("\n" + "=" * 60)
    print(f"  Guardado : {out}  ({len(final):,} caracteres)")
    print(f"  Reporte  : {report_path}")
    if report.counts.get("jobs_total"):
        print(f"  Costo    : ~${report.cost():.3f} USD")
    if report.problems:
        print(f"\n  ⚠ {len(report.problems)} elemento(s) sin transcribir. Detalle en el reporte.")
        print("    Vuelve a correr la misma conversión para reintentar solo esos.")
    else:
        print("  Todo el contenido quedó transcrito.")
    print("=" * 60)
    ui_event("terminado", programa="convert", archivo=str(out), reporte=str(report_path),
             costo=round(report.cost(), 3) if report.counts.get("jobs_total") else 0.0,
             sin_transcribir=len(report.problems))


def main():
    ap = argparse.ArgumentParser(
        description="Convierte un libro (EPUB/PDF/otros) a Markdown limpio, con imágenes transcritas por Gemini.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", help="Archivo de entrada (.epub, .pdf, .docx, ...)")
    ap.add_argument("-o", "--output", default=None,
                    help="Archivo .md de salida (por defecto: mismo nombre con .md)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Modelo de Gemini para imágenes (por defecto: {DEFAULT_MODEL})")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help=f"Transcripciones en paralelo (por defecto: {DEFAULT_WORKERS})")
    ap.add_argument("--yes", action="store_true",
                    help="No preguntar antes de gastar (confirmar automáticamente)")
    args = ap.parse_args()

    output = args.output or str(Path(args.input).with_suffix(".md"))
    convert(args.input, output, args.model, max(1, args.workers), args.yes)


if __name__ == "__main__":
    main()
