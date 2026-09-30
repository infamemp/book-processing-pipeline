#!/usr/bin/env python3
"""
extract.py — Paso 2 del pipeline: libro convertido (.md) → KB (CORE + BIBLIOTECA).

Versión 3.1

CÓMO FUNCIONA
  1. MAP        (Claude)  lee el libro, saca metadatos, dominio, nivel de autoridad
                          sugerido y lo divide en unidades (capítulos).
  2. EXTRACT    (Claude)  una llamada por capítulo; extrae todo en entradas pequeñas.
  3. VERIFY     (Gemini)  una llamada por capítulo; otro modelo compara lo extraído
                          contra el texto: corrige números, agrega lo que faltó y
                          elimina lo inventado.
  4. SYNTHESIS  (Claude)  una llamada; panorama, principios, Modelo Integral y
                          notas de vigencia.
  Al final ARMA los archivos:
      <slug>_core.md         conocimiento completo (tablas, fórmulas, reglas...)
      <slug>_biblioteca.md   catálogos completos (planes, entrenamientos, recetas...)
      <slug>_indice.json     entrada lista para kb_indice.json (sistema de nutrición)
      <slug>_reporte.txt     bitácora, verificación de números y costos

DOS MODOS
  Inmediato (predeterminado): resultado en minutos. El libro completo va en
      caché de 1 hora; cada capítulo lo relee a una fracción del costo.
  Lote (--batch): ~50% más barato; Anthropic entrega en minutos u horas
      (máximo 24 h). Corre el MISMO comando varias veces: cada vez revisa si el
      lote terminó, descarga, avanza a la siguiente pasada y envía el siguiente
      lote. No hay que copiar ningún ID. En lote, cada capítulo se envía con su
      texto y el mapa del libro (no el libro completo), para no pagarlo 14 veces.

  Todo queda guardado en la carpeta de trabajo (_work_<libro>): si algo falla o
  se interrumpe, al volver a correr solo se hace lo que falta.
  Antes de gastar muestra el costo estimado y pide confirmación (--yes la omite).

REQUISITOS
  pip install --upgrade anthropic google-genai
  Variables de entorno ANTHROPIC_API_KEY y GEMINI_API_KEY

USO
  python extract.py --input "libro.md" --output "carpeta_kb"
  python extract.py --input "libro.md" --output "carpeta_kb" --batch
  python extract.py --input "libro.md" --output "carpeta_kb" --units U05,U08   (prueba)
  python extract.py --input "libro.md" --output "carpeta_kb" --stage map       (solo el mapa)
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("Falta el SDK de Anthropic. Instala con:  pip install --upgrade anthropic")

EXTRACTOR_VERSION = "3.1"

# ── Modelos y precios (USD por millón de tokens) ─────────────────────────────
# Fuentes: platform.claude.com/docs y ai.google.dev/gemini-api/docs/pricing (sep 2026).
MODELS = {
    "sonnet": "claude-sonnet-5-5",
    "opus":   "claude-opus-5-5",
    "fable":  "claude-fable-5-1",
}
DEFAULT_MODEL = "sonnet"
PRICES = {  # (entrada, salida, multiplicador de lectura de caché)
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-opus-5-5":   (4.0, 20.0, 0.05),
    "claude-fable-5-1":  (10.0, 50.0, 0.025),
}
CACHE_WRITE_MULT = 2.0          # escritura de caché de 1 hora
CACHE_TTL_SECONDS = 3300        # margen: se considera vencida a los 55 min
BATCH_DISCOUNT = 0.5
CACHE = {"type": "ephemeral", "ttl": "1h"}

GEMINI_MODEL = "gemini-3.8-flash"
# Gemini 3.8 Flash: $0.75 / $3.75 hasta el 31 dic 2026; $1.50 / $7.50 desde el 1 ene 2027.
GEMINI_PRICE = (0.75, 3.75) if datetime.now() < datetime(2027, 1, 1) else (1.50, 7.50)

MAX_TOKENS = {"map": 32000, "extract": 64000, "verify": 65536, "synthesis": 64000}
EFFORT = {"map": "medium", "extract": "low", "synthesis": "medium"}
DEFAULT_WORKERS = 3
CALL_RETRIES = 3

CORE_SECTIONS = [
    ("C01", "Overview & Scope"),
    ("C02", "Philosophy & Core Principles"),
    ("C03", "Integral Model"),
    ("C04", "Mechanisms"),
    ("C05", "Glossary"),
    ("C06", "Quantitative Reference"),
    ("C07", "Testing & Assessment"),
    ("C08", "Methodology & Progression"),
    ("C09", "Decision Rules & Heuristics"),
    ("C10", "Applied Guidance"),
    ("C11", "Recovery, Monitoring & Lifestyle"),
    ("C12", "Adaptations by Population / Context"),
    ("C13", "Contraindications, Cautions & Safety Limits"),
    ("C14", "Formulas & Calculations"),
    ("C15", "Evidence & Key References"),
    ("C16", "Notable Statements"),
    ("C17", "Validity Notes"),
    ("C18", "Library Index"),
]
LIBRARY_SECTIONS = [
    ("L1", "Plans & Programs"),
    ("L2", "Workouts & Protocols"),
    ("L3", "Exercises & Technique"),
    ("L4", "Recipes, Menus & Meal Plans"),
    ("L5", "Worksheets, Questionnaires & Templates"),
]
VALID_DEST = {c for c, _ in CORE_SECTIONS} | {c for c, _ in LIBRARY_SECTIONS} | {"SUMMARY", "LOG", "DELETE"}

ENTRY_RE = re.compile(r'<<<ENTRY\s+((?:\w+\s*=\s*"[^"]*"\s*)+)>>>(.*?)<<<END>>>', re.S)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

UNIT_ONLY_NOTE = ("NOTE: in this call only the text of the unit is provided (inside <unit>), "
                  "not the whole book. Use the book map for cross-references.\n\n")

PRINT_LOCK = threading.Lock()


def say(msg):
    with PRINT_LOCK:
        print(msg, flush=True)


# ═════════════════════════════════════════════════════════════════════════════
# Utilidades
# ═════════════════════════════════════════════════════════════════════════════

def load_prompts(path):
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^<!-- (?:PROMPT|TASK): (\w+) -->\s*$", text, flags=re.M)
    blocks = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    for k in ("system", "map", "extract", "synthesis", "verify"):
        if k not in blocks:
            sys.exit(f"ERROR: al archivo de instrucciones le falta el bloque '{k}'.")
    return blocks


def fill(template, **fields):
    for k, v in fields.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def parse_entries(text):
    out = []
    for m in ENTRY_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        out.append({
            "dest": attrs.get("dest", "").strip().upper(),
            "title": attrs.get("title", "").strip(),
            "replace": attrs.get("replace", "").strip().upper(),
            "body": m.group(2).strip(),
        })
    return out


def parse_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("no se encontró JSON en la respuesta")
    return json.loads(t[a:b + 1])


def safe_slug(s):
    s = re.sub(r"[^a-z0-9\-]+", "-", (s or "").lower())
    return re.sub(r"-{2,}", "-", s).strip("-")[:70] or "libro"


def est_tokens(text):
    return len(text) // 4


def money(x):
    return f"${x:,.2f}"



# ═════════════════════════════════════════════════════════════════════════════
# Registro de uso y costos
# ═════════════════════════════════════════════════════════════════════════════

class Usage:
    def __init__(self, workdir):
        self.file = workdir / "usage.jsonl"
        self.lock = threading.Lock()

    def log(self, u):
        with self.lock:
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(json.dumps(u) + "\n")

    def rows(self):
        if not self.file.exists():
            return []
        return [json.loads(x) for x in self.file.read_text(encoding="utf-8").splitlines() if x.strip()]

    def total_cost(self):
        tot, agg = 0.0, {}
        for u in self.rows():
            tot += u.get("cost", 0)
            stage = u["label"].split(" ")[0]
            agg[stage] = agg.get(stage, 0) + u.get("cost", 0)
        return tot, agg

    def cache_alive(self, model):
        """¿Hubo una llamada inmediata con este modelo hace menos de 55 min?"""
        for u in reversed(self.rows()):
            if u.get("model") == model and not u.get("batch"):
                t = datetime.fromisoformat(u["time"])
                return (datetime.now() - t).total_seconds() < CACHE_TTL_SECONDS
        return False


def claude_cost(model, u, batch):
    pin, pout, rmult = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    c = (u.get("input", 0) * pin
         + u.get("cache_write", 0) * pin * CACHE_WRITE_MULT
         + u.get("cache_read", 0) * pin * rmult
         + u.get("output", 0) * pout) / 1_000_000
    return c * (BATCH_DISCOUNT if batch else 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# Claude (inmediato y lote)
# ═════════════════════════════════════════════════════════════════════════════

class Claude:
    def __init__(self, model, system, book, workdir, usage):
        self.client = anthropic.Anthropic(max_retries=5, timeout=3600)
        self.model = model
        self.system = system
        self.book = book
        self.workdir = workdir
        self.usage = usage

    # ── contenido de los mensajes ──
    def book_block(self):
        return {"type": "text", "text": "<book>\n" + self.book + "\n</book>", "cache_control": CACHE}

    def content_full_book(self, task):
        return [self.book_block(), {"type": "text", "text": task}]

    @staticmethod
    def content_unit(unit_text, task):
        return [{"type": "text", "text": "<unit>\n" + unit_text + "\n</unit>"},
                {"type": "text", "text": UNIT_ONLY_NOTE + task}]

    def params(self, content, max_tokens, effort):
        return dict(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            system=[{"type": "text", "text": self.system}],
            messages=[{"role": "user", "content": content}],
        )

    def count_book_tokens(self):
        try:
            r = self.client.messages.count_tokens(
                model=self.model,
                system=[{"type": "text", "text": self.system}],
                messages=[{"role": "user", "content": self.content_full_book("x")}],
            )
            return r.input_tokens
        except Exception:
            return int((len(self.system) + len(self.book)) / 3.3)

    def _record(self, label, msg, batch):
        us = msg.usage
        u = {
            "label": label, "model": self.model, "batch": batch,
            "input": us.input_tokens or 0,
            "cache_write": getattr(us, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(us, "cache_read_input_tokens", 0) or 0,
            "output": us.output_tokens or 0,
            "stop": msg.stop_reason,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        u["cost"] = round(claude_cost(self.model, u, batch), 4)
        self.usage.log(u)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    # ── inmediato ──
    def call(self, params, label):
        last = None
        for attempt in range(CALL_RETRIES):
            try:
                with self.client.messages.stream(**params) as stream:
                    final = stream.get_final_message()
                return self._record(label, final, False), final.stop_reason
            except anthropic.APIStatusError as e:
                if e.status_code not in (429, 500, 502, 503, 529):
                    raise
                last = e
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
                last = e
            wait = 30 * (attempt + 1)
            say(f"    [{label}] error temporal ({str(last)[:80]}); reintento en {wait}s...")
            time.sleep(wait)
        raise RuntimeError(f"{label}: falló tras {CALL_RETRIES} intentos: {last}")

    def run_immediate(self, jobs, workers):
        """jobs: lista de dict(id, label, params, out). Guarda cada resultado en job['out']."""
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {}
            for j in jobs:
                futs[ex.submit(self.call, j["params"], j["label"])] = j
                if len(futs) == 1 and len(jobs) > 1 and not self.usage.cache_alive(self.model):
                    # la primera llamada escribe la caché; las demás esperan a que exista
                    time.sleep(20)
            for fut in as_completed(futs):
                j = futs[fut]
                try:
                    text, stop = fut.result()
                    j["out"].write_text(text, encoding="utf-8")
                    if stop == "max_tokens":
                        j["out"].with_suffix(".TRUNCATED").write_text("1", encoding="utf-8")
                    n = len(parse_entries(text))
                    say(f"  ✓ {j['label']}" + (f": {n} entradas" if n else "")
                        + ("  ⚠ TRUNCADO" if stop == "max_tokens" else ""))
                except Exception as e:
                    msg = str(e)
                    if "credit balance" in msg:
                        msg = "saldo insuficiente en la cuenta de Anthropic (Plans & Billing)"
                    errors.append(f"{j['label']}: {msg[:200]}")
                    say(f"  ✗ {j['label']}: {msg[:120]}")
        return errors

    # ── lote ──
    def batch_state_file(self, stage):
        return self.workdir / f"batch_{stage}.json"

    def run_batch(self, stage, jobs):
        """
        Envía o recoge el lote de una pasada.
        Devuelve 'done' (resultados guardados), 'waiting' (lote en proceso) o
        'submitted' (lote recién enviado).
        """
        sf = self.batch_state_file(stage)
        if sf.exists():
            st = json.loads(sf.read_text(encoding="utf-8"))
            b = self.client.messages.batches.retrieve(st["batch_id"])
            if b.processing_status != "ended":
                rc = b.request_counts
                say(f"\n  Lote {stage} en proceso — listos {rc.succeeded}, procesando {rc.processing}, "
                    f"errores {rc.errored}. Enviado: {st['submitted']}")
                return "waiting"
            say(f"\n  Lote {stage} terminado. Descargando resultados...")
            outs = {j["custom_id"]: j for j in st["jobs"]}
            failed = []
            for r in self.client.messages.batches.results(st["batch_id"]):
                j = outs.get(r.custom_id)
                if not j:
                    continue
                if r.result.type == "succeeded":
                    msg = r.result.message
                    text = self._record(j["label"], msg, True)
                    out = Path(j["out"])
                    out.write_text(text, encoding="utf-8")
                    if msg.stop_reason == "max_tokens":
                        out.with_suffix(".TRUNCATED").write_text("1", encoding="utf-8")
                    say(f"  ✓ {j['label']}: {len(parse_entries(text))} entradas"
                        + ("  ⚠ TRUNCADO" if msg.stop_reason == "max_tokens" else ""))
                else:
                    err = getattr(r.result, "error", r.result.type)
                    failed.append(j["label"])
                    say(f"  ✗ {j['label']}: {str(err)[:150]}")
            sf.rename(sf.with_name(f"batch_{stage}_{st['batch_id'][-8:]}_done.json"))
            if failed:
                say(f"  {len(failed)} solicitud(es) fallaron; se reenviarán en la siguiente corrida.")
            return "done"

        if not jobs:
            return "done"
        requests = [{"custom_id": j["id"], "params": j["params"]} for j in jobs]
        b = self.client.messages.batches.create(requests=requests)
        sf.write_text(json.dumps({
            "batch_id": b.id,
            "submitted": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "jobs": [{"custom_id": j["id"], "label": j["label"], "out": str(j["out"])} for j in jobs],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        say(f"\n  Lote {stage} enviado ({len(jobs)} solicitud(es)). ID: {b.id}")
        return "submitted"


# ═════════════════════════════════════════════════════════════════════════════
# Gemini (verificación)
# ═════════════════════════════════════════════════════════════════════════════

class GeminiVerifier:
    def __init__(self, system, usage):
        self.system = system
        self.usage = usage
        self.client = None
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=key)
        except ImportError:
            say("AVISO: falta google-genai (pip install --upgrade google-genai).")

    def call(self, unit_text, task, label):
        from google.genai import types
        cfg = types.GenerateContentConfig(
            system_instruction=self.system,
            max_output_tokens=MAX_TOKENS["verify"],
            thinking_config=types.ThinkingConfig(thinking_level="medium"),
        )
        contents = "<unit>\n" + unit_text + "\n</unit>\n\n" + UNIT_ONLY_NOTE + task
        last = ""
        for attempt in range(CALL_RETRIES):
            try:
                r = self.client.models.generate_content(model=GEMINI_MODEL, contents=contents, config=cfg)
                um = r.usage_metadata
                tin = (um.prompt_token_count or 0) if um else 0
                tout = ((um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)) if um else 0
                cost = (tin * GEMINI_PRICE[0] + tout * GEMINI_PRICE[1]) / 1_000_000
                self.usage.log({"label": label, "model": GEMINI_MODEL, "batch": False, "input": tin,
                                "output": tout, "time": datetime.now().isoformat(timespec="seconds"),
                                "cost": round(cost, 4)})
                cand = r.candidates[0] if r.candidates else None
                finish = str(getattr(cand, "finish_reason", "") or "")
                text = ""
                try:
                    text = (r.text or "").strip()
                except Exception:
                    pass
                if "MAX_TOKENS" in finish:
                    return text, "truncated"
                if text:
                    return text, "ok"
                last = f"respuesta vacía ({finish})"
            except Exception as e:
                last = str(e)[:200]
            if attempt < CALL_RETRIES - 1:
                time.sleep(10 * (attempt + 1))
        raise RuntimeError(f"{label}: {last}")


# ═════════════════════════════════════════════════════════════════════════════
# Etapas
# ═════════════════════════════════════════════════════════════════════════════

def confirm(msg_lines, assume_yes):
    print("\n" + "-" * 64)
    for ln in msg_lines:
        print("  " + ln)
    print("-" * 64)
    if assume_yes:
        return True
    try:
        return input("¿Continuar? [s/N]: ").strip().lower() in ("s", "si", "sí", "y", "yes")
    except EOFError:
        print("Sin respuesta. Usa --yes para correr sin pregunta.")
        return False


def print_map(bmap, units):
    md = bmap.get("metadata", {})
    print("\n" + "=" * 64)
    print(f"  {md.get('title', '')} — {', '.join(md.get('authors', []))} ({md.get('year', '')})")
    print(f"  Dominio(s): {', '.join(bmap.get('domains', []))}"
          + (f"   Temas: {', '.join(bmap.get('conditions', []))}" if bmap.get("conditions") else ""))
    print(f"  Nivel sugerido: {bmap.get('authority_level', '?')} — {bmap.get('authority_rationale', '')[:120]}")
    if bmap.get("proposed_domain"):
        print(f"  [PROPUESTA DE DOMINIO NUEVO] {bmap['proposed_domain']}")
    print("=" * 64)
    print("  Unidades:")
    for u in units:
        print(f"   {u['id']:<5} {u.get('kind', ''):<8} ~{u['chars'] // 4:>7,} tok   {u.get('title', '')[:60]}")
    print()


def numbered_entries(entries):
    parts = []
    for i, e in enumerate(entries, 1):
        parts.append(f'[E{i:02d}] <<<ENTRY dest="{e["dest"]}" title="{e["title"]}">>>\n{e["body"]}\n<<<END>>>')
    return "\n\n".join(parts)


def content_entries(text):
    return [e for e in parse_entries(text) if e["dest"] not in ("SUMMARY", "LOG")]


def verify_units(gemini, prompts, workdir, book, units, workers):
    todo = [u for u in units
            if (workdir / f"{u['id']}.extract.txt").exists()
            and not (workdir / f"{u['id']}.verify.txt").exists()]
    if not todo:
        return []
    if gemini.client is None:
        return ["VERIFY omitido: falta GEMINI_API_KEY o google-genai"]
    say(f"\nVERIFY (Gemini): {len(todo)} unidad(es)...")
    errors = []

    def work(u):
        ents = content_entries((workdir / f"{u['id']}.extract.txt").read_text(encoding="utf-8"))
        task = fill(prompts["verify"], unit_id=u["id"], unit_title=u.get("title", ""),
                    unit_start=u["start_line"], unit_end=u["end"], entries=numbered_entries(ents))
        text, status = gemini.call(book[u["a"]:u["b"]], task, f"VERIFY {u['id']}")
        (workdir / f"{u['id']}.verify.txt").write_text(text, encoding="utf-8")
        ops = parse_entries(text)
        rep = sum(1 for o in ops if o["replace"])
        dele = sum(1 for o in ops if o["dest"] == "DELETE")
        add = sum(1 for o in ops if not o["replace"] and o["dest"] not in ("DELETE", "LOG"))
        say(f"  ✓ VERIFY {u['id']}: {rep} corregidas, {add} agregadas, {dele} eliminadas"
            + ("  ⚠ TRUNCADO" if status == "truncated" else ""))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(work, u): u for u in todo}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                errors.append(f"VERIFY {futs[fut]['id']}: {str(e)[:200]}")
                say(f"  ✗ VERIFY {futs[fut]['id']}: {str(e)[:120]}")
    return errors


def synthesis_task(prompts, workdir, bmap_compact, units):
    summaries, index = [], {}
    for u in units:
        p = workdir / f"{u['id']}.extract.txt"
        if not p.exists():
            continue
        for e in parse_entries(p.read_text(encoding="utf-8")):
            if e["dest"] == "SUMMARY":
                summaries.append(f"### {u['id']} — {u.get('title', '')}\n{e['body']}")
            elif e["dest"] in VALID_DEST and e["dest"] not in ("LOG", "DELETE"):
                index.setdefault(e["dest"], []).append(e["title"])
    entry_index = "\n".join(f"{d}: " + " · ".join(t) for d, t in sorted(index.items()))
    return fill(prompts["synthesis"], map=bmap_compact, summaries="\n\n".join(summaries), entry_index=entry_index)



# ═════════════════════════════════════════════════════════════════════════════
# Unidades
# ═════════════════════════════════════════════════════════════════════════════

def locate_units(book, units):
    """Ubica el inicio de cada unidad en el libro. Devuelve lista con 'a' y 'b' (posiciones)."""
    lines = book.split("\n")
    offsets, pos = [], 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1

    def find_line(start_text, from_idx):
        target = start_text.strip()
        for i in range(from_idx, len(lines)):
            if lines[i].strip() == target:
                return i
        for i in range(from_idx, len(lines)):       # coincidencia parcial
            if target and target in lines[i]:
                return i
        return None

    located, idx, problems = [], 0, []
    for u in units:
        i = find_line(u.get("start", ""), idx)
        if i is None:
            problems.append(f"{u['id']}: no encontré su línea de inicio: {u.get('start', '')[:80]}")
            continue
        located.append(dict(u, line=i))
        idx = i + 1
    if located:
        located[0]["line"] = 0   # la primera unidad cubre desde el inicio
    for k, u in enumerate(located):
        u["a"] = offsets[u["line"]]
        u["b"] = offsets[located[k + 1]["line"]] if k + 1 < len(located) else len(book)
        u["end"] = lines[located[k + 1]["line"]].strip() if k + 1 < len(located) else "(end of book)"
        u["start_line"] = lines[u["line"]].strip()
        u["chars"] = u["b"] - u["a"]
    return located, problems


def apply_verify(entries, verify_text):
    """Aplica correcciones/altas/bajas de VERIFY a la lista de entradas de una unidad."""
    ops = parse_entries(verify_text)
    result = list(entries)
    deleted = set()
    logs = []
    for o in ops:
        if o["dest"] == "LOG":
            logs.append(o)
        elif o["dest"] == "DELETE":
            m = re.search(r"E(\d+)", o["title"])
            if m:
                deleted.add(int(m.group(1)))
        elif o["replace"]:
            m = re.search(r"E(\d+)", o["replace"])
            if m and 1 <= int(m.group(1)) <= len(entries):
                k = int(m.group(1)) - 1
                result[k] = dict(o, replace="", verified="corrected")
    final = [e for i, e in enumerate(result, 1) if i not in deleted]
    added = [dict(o, verified="added") for o in ops
             if o["dest"] not in ("LOG", "DELETE") and not o["replace"]]
    return final + added, logs, len(deleted)


# ═════════════════════════════════════════════════════════════════════════════
# Verificación de números (sin IA)
# ═════════════════════════════════════════════════════════════════════════════

NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def numbers_not_in_source(body, source):
    lines = [ln for ln in body.split("\n")
             if not ln.strip().lower().startswith(("tags:", "src:", "evidence:"))
             and "[DERIVED]" not in ln]
    text = "\n".join(lines)
    src_nums = set(NUM_RE.findall(source))
    src_norm = {n.replace(",", ".") for n in src_nums}
    missing = []
    for n in set(NUM_RE.findall(text)):
        if n in src_nums or n.replace(",", ".") in src_norm:
            continue
        if len(n.replace(",", "").replace(".", "")) <= 1:   # 0-9 aparecen en todas partes
            continue
        missing.append(n)
    return sorted(missing)


# ═════════════════════════════════════════════════════════════════════════════
# Armado de archivos
# ═════════════════════════════════════════════════════════════════════════════

def yaml_value(v):
    return json.dumps(v, ensure_ascii=False)


def assemble(workdir, outdir, book, bmap, units, content_units, model, partial, input_name, claude):
    md = bmap.get("metadata", {})
    slug = safe_slug(bmap.get("slug") or f"{(md.get('authors') or ['autor'])[0]}-{md.get('title', '')}")
    abbr = re.sub(r"[^A-Z0-9]", "", (bmap.get("abbreviation") or "BK").upper())[:6] or "BK"

    by_dest = {c: [] for c, _ in CORE_SECTIONS + LIBRARY_SECTIONS}
    logs, warnings, stats = [], [], {"entries": 0, "corrected": 0, "added": 0, "deleted": 0, "bad_dest": 0}

    for u in content_units:
        p = workdir / f"{u['id']}.extract.txt"
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8")
        all_e = parse_entries(raw)
        logs += [dict(e, unit=u["id"]) for e in all_e if e["dest"] == "LOG"]
        ents = [e for e in all_e if e["dest"] not in ("SUMMARY", "LOG")]
        v = workdir / f"{u['id']}.verify.txt"
        if v.exists():
            ents, vlogs, ndel = apply_verify(ents, v.read_text(encoding="utf-8"))
            logs += [dict(e, unit=u["id"]) for e in vlogs]
            stats["deleted"] += ndel
        else:
            warnings.append(f"{u['id']}: sin VERIFY")
        if (workdir / f"{u['id']}.TRUNCATED").exists():
            warnings.append(f"{u['id']}: la extracción se cortó por longitud (revisar; dividir la unidad)")
        src = book[u["a"]:u["b"]]
        for e in ents:
            if e["dest"] not in by_dest:
                stats["bad_dest"] += 1
                warnings.append(f"{u['id']}: entrada con sección desconocida '{e['dest']}' → C10: {e['title'][:60]}")
                e["dest"] = "C10"
            miss = numbers_not_in_source(e["body"], src)
            if miss:
                warnings.append(f"{u['id']} · {e['title'][:60]}: números que no aparecen en el capítulo: {', '.join(miss[:12])}")
            e["unit"] = u["id"]
            stats["entries"] += 1
            stats["corrected"] += e.get("verified") == "corrected"
            stats["added"] += e.get("verified") == "added"
            by_dest[e["dest"]].append(e)

    synth = workdir / "synthesis.txt"
    if synth.exists():
        for e in parse_entries(synth.read_text(encoding="utf-8")):
            if e["dest"] == "LOG":
                logs.append(dict(e, unit="SYNTHESIS"))
            elif e["dest"] in by_dest:
                miss = numbers_not_in_source(e["body"], book)
                if miss:
                    warnings.append(f"SYNTHESIS · {e['title'][:60]}: números que no aparecen en el libro: {', '.join(miss[:12])}")
                e["unit"] = "SYNTHESIS"
                if e["dest"] in ("C01", "C02", "C03"):
                    by_dest[e["dest"]].insert(0, e)
                else:
                    by_dest[e["dest"]].append(e)

    # Glosario: sin duplicados (se queda la definición más completa)
    gl = {}
    for e in by_dest["C05"]:
        k = e["title"].strip().lower()
        if k not in gl or len(e["body"]) > len(gl[k]["body"]):
            gl[k] = e
    by_dest["C05"] = sorted(gl.values(), key=lambda e: e["title"].lower())

    # IDs estables
    for code in by_dest:
        for i, e in enumerate(by_dest[code], 1):
            e["id"] = f"{abbr}-{code}-{i:03d}"

    # Índice de la biblioteca dentro del CORE
    lib_index = []
    for code, name in LIBRARY_SECTIONS:
        if by_dest[code]:
            lib_index.append(f"**{code} {name}**")
            lib_index += [f"- {e['id']} — {e['title']}" for e in by_dest[code]]
            lib_index.append("")
    by_dest["C18"] = [{"id": f"{abbr}-C18-001", "title": "Contents of the library file",
                       "body": "\n".join(lib_index).strip() or "The library file is empty for this book.",
                       "unit": "-"}]

    covered = [u["id"] for u in content_units if (workdir / f"{u['id']}.extract.txt").exists()]
    header = [
        "---",
        f"title: {yaml_value(md.get('title', ''))}",
        f"subtitle: {yaml_value(md.get('subtitle', ''))}",
        f"authors: {yaml_value(md.get('authors', []))}",
        f"edition: {yaml_value(md.get('edition', ''))}",
        f"year: {yaml_value(md.get('year', ''))}",
        f"publisher: {yaml_value(md.get('publisher', ''))}",
        f"language: {yaml_value(md.get('language', ''))}",
        f"domains: {yaml_value(bmap.get('domains', []))}",
        f"conditions: {yaml_value(bmap.get('conditions', []))}",
        f"authority_level_suggested: {yaml_value(bmap.get('authority_level', ''))}",
        f"authority_rationale: {yaml_value(bmap.get('authority_rationale', ''))}",
        f"author_credentials: {yaml_value(bmap.get('author_credentials', []))}",
        f"commercial_interests: {yaml_value(bmap.get('commercial_interests', ''))}",
        f"abbreviation: {yaml_value(abbr)}",
        f"source_file: {yaml_value(input_name)}",
        f"kb_version: {yaml_value(EXTRACTOR_VERSION)}",
        f"extracted: {yaml_value(datetime.now().strftime('%Y-%m-%d'))}",
        f"model: {yaml_value(model)}",
        f"coverage: {yaml_value('partial: ' + ', '.join(covered) if partial else 'complete')}",
        "---",
        "",
    ]
    authors = ", ".join(md.get("authors", []))
    title_line = f"{authors} — {md.get('title', '')} ({md.get('year', '')})"

    def render(sections, kind, companion):
        out = list(header)
        out.append(f"# KB {kind} — {title_line}")
        out.append("")
        if kind == "CORE":
            out.append(f"Companion file: `{companion}` (full plans, workouts, exercises, recipes, "
                       "templates). IDs like `{a}-L2-004` point there.".format(a=abbr))
        else:
            out.append(f"Companion file: `{companion}` (principles, zones, tables, rules, cautions).")
        if partial:
            out.append("")
            out.append(f"> PARTIAL KB — only these units were extracted: {', '.join(covered)}.")
        out.append("")
        for code, name in sections:
            out.append(f"## {code} {name}")
            out.append("")
            ents = by_dest.get(code, [])
            if not ents:
                out.append("No content in this section.")
                out.append("")
                continue
            for e in ents:
                out.append(f"### [{e['id']}] {e['title']}")
                out.append("")
                out.append(e["body"])
                out.append("")
        return "\n".join(out).rstrip() + "\n"

    core_name = f"{slug}_core.md"
    lib_name = f"{slug}_biblioteca.md"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / core_name).write_text(render(CORE_SECTIONS, "CORE", lib_name), encoding="utf-8")
    (outdir / lib_name).write_text(render(LIBRARY_SECTIONS, "LIBRARY", core_name), encoding="utf-8")

    # Entrada para kb_indice.json (sistema de nutrición)
    year = md.get("year", "")
    m = re.search(r"\d{4}", str(year))
    indice = {
        "archivo": core_name,
        "biblioteca": lib_name,
        "titulo": md.get("title", ""),
        "autor": authors,
        "ano": int(m.group(0)) if m else year,
        "nivel": bmap.get("authority_level", ""),
        "dominios": bmap.get("domains", []),
        "temas": bmap.get("conditions", []),
        "nota": bmap.get("authority_rationale", ""),
    }
    (outdir / f"{slug}_indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")

    # Reporte
    total, per_stage = claude.total_cost()
    R = ["REPORTE DE EXTRACCIÓN", "=" * 64,
         f"Libro      : {title_line}",
         f"Entrada    : {input_name}",
         f"Modelo     : {model}",
         f"Fecha      : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
         f"Cobertura  : {'PARCIAL: ' + ', '.join(covered) if partial else 'completa'}",
         "",
         f"Entradas   : {stats['entries']}  (corregidas por VERIFY: {stats['corrected']}, "
         f"agregadas: {stats['added']}, eliminadas: {stats['deleted']})",
         "Por sección:"]
    for code, name in CORE_SECTIONS + LIBRARY_SECTIONS:
        R.append(f"   {code} {name:<45} {len(by_dest.get(code, []))}")
    R += ["", f"Costo total: {money(total)} USD"]
    for k, v in per_stage.items():
        R.append(f"   {k:<10} {money(v)}")
    R += ["", f"AVISOS ({len(warnings)})", "-" * 64]
    R += [f"  - {w}" for w in warnings] or ["  (ninguno)"]
    R += ["", "Nota: 'números que no aparecen en el capítulo' es una revisión automática;",
          "puede ser un valor derivado legítimo o un error. Revisar esos casos.",
          "", "BITÁCORA (LOG)", "-" * 64]
    for lg in logs:
        R.append(f"[{lg.get('unit')}] {lg['title']}")
        R.append(lg["body"])
        R.append("")
    report = outdir / f"{slug}_reporte.txt"
    report.write_text("\n".join(R), encoding="utf-8")
    return outdir / core_name, outdir / lib_name, report, stats, warnings, total


# ═════════════════════════════════════════════════════════════════════════════
# Principal
# ═════════════════════════════════════════════════════════════════════════════

def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="Extrae un KB (CORE + BIBLIOTECA) de un libro convertido (Claude + verificación Gemini).",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--input", required=True, help="Libro convertido (.md) por convert.py")
    ap.add_argument("--output", required=True, help="Carpeta donde se guardan los archivos del KB")
    ap.add_argument("--prompts", default=str(here / "extraction_prompts.md"),
                    help="Archivo de instrucciones (por defecto: extraction_prompts.md junto a este script)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="sonnet (predeterminado), opus o fable")
    ap.add_argument("--batch", action="store_true", help="Modo lote: ~50%% más barato, entrega en minutos u horas")
    ap.add_argument("--stage", default="all", choices=["all", "map", "extract", "verify", "synthesis", "assemble"],
                    help="Correr solo hasta una etapa (predeterminado: all)")
    ap.add_argument("--units", default="", help="Solo estas unidades, ej. U05,U08 (prueba parcial)")
    ap.add_argument("--no-verify", action="store_true", help="Omitir la verificación con Gemini")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Llamadas en paralelo (predeterminado: 3)")
    ap.add_argument("--yes", action="store_true", help="No preguntar antes de gastar")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY. Configúrala con:  $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
    if not args.no_verify and not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Falta GEMINI_API_KEY (necesaria para la verificación). O usa --no-verify.")
    inp = Path(args.input)
    if not inp.exists():
        sys.exit(f"No existe: {inp}")
    model = MODELS.get(args.model, args.model)
    if model not in PRICES:
        sys.exit(f"Modelo no reconocido: {args.model}. Usa sonnet, opus o fable.")

    prompts = load_prompts(args.prompts)
    book = inp.read_text(encoding="utf-8")
    outdir = Path(args.output)
    workdir = outdir / f"_work_{safe_slug(inp.stem)}"
    workdir.mkdir(parents=True, exist_ok=True)

    usage = Usage(workdir)
    claude = Claude(model, prompts["system"], book, workdir, usage)
    gemini = GeminiVerifier(prompts["system"], usage)
    mode = "LOTE" if args.batch else "INMEDIATO"
    pin, pout, rmult = PRICES[model]
    disc = BATCH_DISCOUNT if args.batch else 1.0
    gin, gout = GEMINI_PRICE[0] / 1e6, GEMINI_PRICE[1] / 1e6

    print(f"\nLibro : {inp.name}")
    print(f"Modo  : {mode}   Modelo: {model}   Verificación: "
          f"{'no' if args.no_verify else GEMINI_MODEL}")
    book_tokens = claude.count_book_tokens()
    print(f"Tokens del libro: ~{book_tokens:,}")

    # ── 1) MAP ──────────────────────────────────────────────────────────────
    map_file, map_raw = workdir / "map.json", workdir / "map_raw.txt"
    if not map_file.exists():
        job = {"id": "MAP", "label": "MAP", "out": map_raw,
               "params": claude.params(claude.content_full_book(prompts["map"]), MAX_TOKENS["map"], EFFORT["map"])}
        pending_batch = claude.batch_state_file("map").exists()
        if not map_raw.exists() and not pending_batch:
            if args.batch:
                est = (book_tokens * pin + 9000 * pout) / 1e6 * disc
            else:
                est = (book_tokens * pin * CACHE_WRITE_MULT + 9000 * pout) / 1e6
            if not confirm([f"Pasada 1 — MAP ({model}, {mode.lower()})",
                            f"Costo estimado: ~{money(est)} USD"], args.yes):
                sys.exit("Cancelado.")
        if not map_raw.exists():
            if args.batch:
                st = claude.run_batch("map", [job])
                if st != "done" or not map_raw.exists():
                    print("\n  Vuelve a correr el MISMO comando más tarde para continuar.")
                    return
            else:
                say("\nMAP: leyendo el libro completo...")
                errs = claude.run_immediate([job], 1)
                if errs:
                    sys.exit("No se pudo completar el MAP.")
        try:
            data = parse_json(map_raw.read_text(encoding="utf-8"))
        except Exception as e:
            sys.exit(f"ERROR: MAP no devolvió un JSON válido ({e}). Revisa {map_raw}")
        map_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    bmap = json.loads(map_file.read_text(encoding="utf-8"))
    units, problems = locate_units(book, bmap.get("units", []))
    for p in problems:
        print(f"  AVISO: {p}")
    if not units:
        sys.exit("ERROR: no se pudo ubicar ninguna unidad del MAP en el libro. Revisa map_raw.txt")
    print_map(bmap, units)
    if args.stage == "map":
        print("MAP listo. Para probar algunos capítulos usa --units con los IDs de arriba.")
        return

    content_units = [u for u in units if u.get("kind") == "content"]
    partial = False
    if args.units:
        wanted = {x.strip().upper() for x in args.units.split(",") if x.strip()}
        content_units = [u for u in units if u["id"].upper() in wanted]
        missing = wanted - {u["id"].upper() for u in content_units}
        if missing:
            sys.exit(f"Unidades no encontradas: {', '.join(sorted(missing))}")
        partial = True

    bmap_compact = json.dumps({k: bmap.get(k) for k in
                               ("metadata", "domains", "conditions", "abbreviation", "thesis", "units", "cross_unit_items")},
                              ensure_ascii=False)
    map_tokens = len(bmap_compact) // 4
    errors = []

    def extract_jobs():
        jobs = []
        for u in content_units:
            out = workdir / f"{u['id']}.extract.txt"
            if out.exists():
                continue
            task = fill(prompts["extract"], map=bmap_compact, unit_id=u["id"], unit_title=u.get("title", ""),
                        unit_start=u["start_line"], unit_end=u["end"])
            content = (claude.content_unit(book[u["a"]:u["b"]], task) if args.batch
                       else claude.content_full_book(task))
            jobs.append({"id": f"EXTRACT-{u['id']}", "label": f"EXTRACT {u['id']}", "out": out, "unit": u,
                         "params": claude.params(content, MAX_TOKENS["extract"], EFFORT["extract"])})
        return jobs

    def estimate(jobs_ext, verify_units_list, do_synth):
        lines, total = [], 0.0
        cache_needed = not args.batch and not usage.cache_alive(model) and (jobs_ext or do_synth)
        if cache_needed:
            c = book_tokens * pin * CACHE_WRITE_MULT / 1e6
            lines.append(f"Guardar el libro en caché (1 h)        ~{money(c)}")
            total += c
        if jobs_ext:
            c = 0.0
            for j in jobs_ext:
                ut = j["unit"]["chars"] // 4
                out_t = 0.6 * ut + 3000
                inp_t = (ut + map_tokens + 3500) * pin if args.batch else book_tokens * pin * rmult
                c += (inp_t + out_t * pout) / 1e6 * disc
            lines.append(f"EXTRACT   {len(jobs_ext):>2} unidad(es) (Claude)       ~{money(c)}")
            total += c
        if verify_units_list:
            c = sum((1.6 * (u["chars"] // 4) + 4000) * gin + (0.15 * (u["chars"] // 4) + 4000) * gout
                    for u in verify_units_list)
            lines.append(f"VERIFY    {len(verify_units_list):>2} unidad(es) (Gemini)       ~{money(c)}")
            total += c
        if do_synth:
            c = ((book_tokens * pin if args.batch else book_tokens * pin * rmult) + 20000 * pout) / 1e6 * disc
            lines.append(f"SYNTHESIS  1 llamada (Claude)           ~{money(c)}")
            total += c
        lines.append(f"Total estimado: ~{money(total)} USD" + ("  (modo lote, -50%)" if args.batch else ""))
        return lines

    synth_out = workdir / "synthesis.txt"
    want_synth = not partial and args.stage in ("all", "synthesis", "assemble") and not synth_out.exists()

    # ── 2) EXTRACT ──────────────────────────────────────────────────────────
    jobs = extract_jobs()
    if args.batch and claude.batch_state_file("extract").exists():
        st = claude.run_batch("extract", [])
        if st != "done":
            print("\n  Vuelve a correr el MISMO comando más tarde para continuar.")
            return
        jobs = extract_jobs()
    if jobs:
        ver_list = [] if args.no_verify else [j["unit"] for j in jobs]
        if not confirm([f"Pasadas pendientes ({model}, {mode.lower()}):"]
                       + estimate(jobs, ver_list, want_synth), args.yes):
            sys.exit("Cancelado. Lo ya hecho quedó guardado en la carpeta de trabajo.")
        if args.batch:
            claude.run_batch("extract", jobs)
            print("\n  Lote enviado. Anthropic suele entregar en minutos u horas (máx. 24 h).")
            print("  Vuelve a correr el MISMO comando más tarde para descargar y continuar.")
            return
        say(f"\nEXTRACT: {len(jobs)} unidad(es), {args.workers} en paralelo...")
        errors += claude.run_immediate(jobs, max(1, args.workers))
    if args.stage == "extract":
        return

    extracted = [u for u in content_units if (workdir / f"{u['id']}.extract.txt").exists()]
    if not extracted:
        print("\nNo hay capítulos extraídos todavía; no se generan archivos.")
        for e in errors:
            print(f"  - {e}")
        return

    # ── 3) VERIFY (Gemini) ─────────────────────────────────────────────────
    if not args.no_verify:
        errors += verify_units(gemini, prompts, workdir, book, content_units, max(1, args.workers))
    if args.stage == "verify":
        return

    # ── 4) SYNTHESIS ────────────────────────────────────────────────────────
    if want_synth:
        missing = [u["id"] for u in content_units if not (workdir / f"{u['id']}.extract.txt").exists()]
        if missing:
            print(f"\nSYNTHESIS pospuesta: faltan unidades por extraer: {', '.join(missing)}")
        else:
            task = synthesis_task(prompts, workdir, bmap_compact, content_units)
            job = {"id": "SYNTHESIS", "label": "SYNTHESIS", "out": synth_out,
                   "params": claude.params(claude.content_full_book(task), MAX_TOKENS["synthesis"], EFFORT["synthesis"])}
            if args.batch:
                st = claude.run_batch("synthesis", [job] if not claude.batch_state_file("synthesis").exists() else [])
                if st != "done" or not synth_out.exists():
                    print("\n  Vuelve a correr el MISMO comando más tarde para terminar.")
                    return
            else:
                if usage.cache_alive(model) or confirm(estimate([], [], True), args.yes):
                    say("\nSYNTHESIS: panorama, principios, Modelo Integral y notas de vigencia...")
                    errors += claude.run_immediate([job], 1)
    if args.stage == "synthesis":
        return

    # ── 5) ARMADO ───────────────────────────────────────────────────────────
    core, lib, report, stats, warnings, total = assemble(
        workdir, outdir, book, bmap, units, content_units, model, partial, inp.name, usage)

    print("\n" + "=" * 64)
    print(f"  CORE       : {core}")
    print(f"  BIBLIOTECA : {lib}")
    print(f"  Reporte    : {report}")
    print(f"  Entradas   : {stats['entries']}  (VERIFY corrigió {stats['corrected']}, agregó {stats['added']}, "
          f"eliminó {stats['deleted']})")
    print(f"  Avisos     : {len(warnings)}   Costo acumulado: {money(total)} USD")
    if errors:
        print(f"\n  ⚠ {len(errors)} problema(s):")
        for e in errors:
            print(f"    - {e}")
        print("  Vuelve a correr el mismo comando: solo se repite lo que falta.")
    if partial:
        print("\n  KB PARCIAL (prueba). Para el libro completo corre sin --units.")
    print("=" * 64)


if __name__ == "__main__":
    main()
