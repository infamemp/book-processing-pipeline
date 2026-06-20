#!/usr/bin/env python3
"""
extract_kb.py — Extracción de KB completo por la API de Claude.

El libro entra COMPLETO en una sola llamada. Sin batches. Sin pérdida de contexto.

MODOS:
  immediate (default) : Resultado inmediato.
  batch               : Batch API — 50% más barato, entrega en ~24h.
  --check BATCH_ID    : Descarga resultados de un batch ya enviado.

ENTRADA:
  Un solo libro (.md) o una carpeta con varios libros (.md).
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("SDK no encontrado. Instala con:  pip install anthropic")

# ---------------------------------------------------------------------------
# Tarifas por millón de tokens (USD) — fuente: docs.anthropic.com
# ---------------------------------------------------------------------------
RATES = {
    "claude-opus-4-8": {
        "in": 5.0,  "out": 25.0,
        "batch_in": 2.50, "batch_out": 12.50,
        "max_tokens": 128000,
    },
    "claude-sonnet-4-6": {
        "in": 3.0,  "out": 15.0,
        "batch_in": 1.50, "batch_out": 7.50,
        "max_tokens": 64000,
    },
}

BATCH_MAX_TOKENS   = 200000
BATCH_BETA_HEADER  = "output-300k-2026-03-24"

# Aliases cortos para --model
MODEL_ALIASES = {
    "opus":   "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def slugify(s, maxlen=60):
    s = Path(s).stem
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.UNICODE)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "kb"


def load_books(input_path):
    """Devuelve [(title, content)]. Acepta un archivo .md o una carpeta."""
    p = Path(input_path)
    if p.is_file():
        return [(p.stem, p.read_text(encoding="utf-8"))]
    if p.is_dir():
        books = sorted(p.glob("*.md"))
        if not books:
            sys.exit(f"No se encontraron archivos .md en '{input_path}'.")
        return [(f.stem, f.read_text(encoding="utf-8")) for f in books]
    sys.exit(f"'{input_path}' no existe.")


def build_message(title, content, book_meta):
    meta = book_meta if book_meta else title
    return f"[SRC metadata: {meta}]\n\n---\n\n{content}"


def est_cost(tok_in, tok_out, model, mode):
    r = RATES[model]
    ki = r["batch_in"]  if mode == "batch" else r["in"]
    ko = r["batch_out"] if mode == "batch" else r["out"]
    return (tok_in * ki + tok_out * ko) / 1_000_000


def check_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "\nFalta la API key. Configúrala con:\n"
            "  $env:ANTHROPIC_API_KEY='sk-ant-...'\n"
        )


# ---------------------------------------------------------------------------
# MODO IMMEDIATE
# ---------------------------------------------------------------------------
def mode_immediate(args, system_prompt, books, client):
    os.makedirs(args.output, exist_ok=True)
    max_tokens = RATES[args.model]["max_tokens"]
    cache_ctrl  = {"type": "ephemeral"}
    totals = {"cost": 0.0, "ok": 0, "err": 0, "trunc": 0}

    for i, (title, content) in enumerate(books):
        out_file = Path(args.output) / f"{slugify(title)}_kb.md"

        if out_file.exists() and out_file.stat().st_size > 0 and not args.force:
            print(f"[{i+1}/{len(books)}] SKIP (ya existe): {title[:55]}")
            continue

        user_msg    = build_message(title, content, args.book_meta if len(books) == 1 else "")
        tok_in_est  = (len(system_prompt) + len(user_msg)) // 4
        cost_est    = est_cost(tok_in_est, 60000, args.model, "immediate")

        print(f"\n[{i+1}/{len(books)}] {title[:60]}")
        print(f"  Input ~{tok_in_est:,} tokens  |  Costo est. ~${cost_est:.2f}")
        print(f"  Procesando...", end="", flush=True)

        t0 = time.time()
        try:
            parts = []
            with client.messages.stream(
                model=args.model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system_prompt, "cache_control": cache_ctrl}],
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                for chunk in stream.text_stream:
                    parts.append(chunk)
                final = stream.get_final_message()

            out_file.write_text("".join(parts), encoding="utf-8")

            u     = final.usage
            cost  = est_cost(u.input_tokens, u.output_tokens, args.model, "immediate")
            trunc = final.stop_reason == "max_tokens"
            totals["cost"] += cost
            totals["ok"]   += 1
            totals["trunc"] += int(trunc)

            print(f" listo  {time.time()-t0:.0f}s"
                  f"  in={u.input_tokens:,}  out={u.output_tokens:,}"
                  f"  ${cost:.3f}"
                  + ("  ⚠ TRUNCADO — usa --mode batch" if trunc else ""))
            print(f"  → {out_file}")

        except Exception as e:
            totals["err"] += 1
            print(f" ERROR: {e}")

        if i < len(books) - 1:
            time.sleep(1)

    _print_summary(totals, args.output)


# ---------------------------------------------------------------------------
# MODO BATCH — ENVÍO
# ---------------------------------------------------------------------------
def mode_batch_submit(args, system_prompt, books, client):
    os.makedirs(args.output, exist_ok=True)
    cache_ctrl = {"type": "ephemeral"}
    requests   = []
    cost_total = 0.0

    print(f"\nPreparando {len(books)} libro(s) para el Batch API...\n")

    for title, content in books:
        user_msg   = build_message(title, content, args.book_meta if len(books) == 1 else "")
        tok_in_est = (len(system_prompt) + len(user_msg)) // 4
        cost_est   = est_cost(tok_in_est, 80000, args.model, "batch")
        cost_total += cost_est
        print(f"  {title[:58]:<58}  ~{tok_in_est:,} tokens  ~${cost_est:.2f}")

        requests.append({
            "custom_id": slugify(title),
            "params": {
                "model":      args.model,
                "max_tokens": BATCH_MAX_TOKENS,
                "system":     [{"type": "text", "text": system_prompt, "cache_control": cache_ctrl}],
                "messages":   [{"role": "user", "content": user_msg}],
            },
        })

    print(f"\n  Costo estimado : ~${cost_total:.2f} USD (50% desc. Batch API)")
    print(f"  Entrega        : máximo 24 horas")
    print(f"\nEnviando...", end="", flush=True)

    try:
        batch = client.messages.batches.create(
            requests=requests,
            extra_headers={"anthropic-beta": BATCH_BETA_HEADER},
        )
    except Exception:
        batch = client.messages.batches.create(requests=requests)

    batch_id  = batch.id
    info_file = Path(args.output) / "batch_pending.json"
    info_file.write_text(json.dumps({
        "batch_id":          batch_id,
        "submitted_at":      datetime.now(timezone.utc).isoformat(),
        "model":             args.model,
        "output_folder":     str(args.output),
        "estimated_cost_usd": round(cost_total, 4),
        "books": [{"custom_id": slugify(t), "title": t} for t, _ in books],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f" enviado.\n")
    print(f"{'='*60}")
    print(f"  Batch ID  : {batch_id}")
    print(f"  Info      : {info_file}")
    print(f"\nCuando esté listo descarga con:")
    print(f"  python extract_kb.py --check {batch_id} --output \"{args.output}\"")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# MODO BATCH — CONSULTA Y DESCARGA
# ---------------------------------------------------------------------------
def mode_batch_check(args, client):
    os.makedirs(args.output, exist_ok=True)
    batch_id = args.check

    print(f"Consultando batch: {batch_id}")
    try:
        batch = client.messages.batches.retrieve(batch_id)
    except Exception as e:
        sys.exit(f"Error: {e}")

    status = batch.processing_status
    print(f"Estado : {status}")

    if hasattr(batch, "request_counts"):
        rc = batch.request_counts
        print(f"  Procesando: {rc.processing}  |  Listos: {rc.succeeded}  |  Errores: {rc.errored}")

    if status != "ended":
        print(f"\nAún no está listo. Vuelve a consultar con:")
        print(f"  python extract_kb.py --check {batch_id} --output \"{args.output}\"")
        return

    print("\nBatch listo. Descargando...")

    # Carga títulos guardados si existen
    info_file  = Path(args.output) / "batch_pending.json"
    book_titles = {}
    if info_file.exists():
        info = json.loads(info_file.read_text(encoding="utf-8"))
        book_titles = {b["custom_id"]: b["title"] for b in info.get("books", [])}

    ok = err = 0
    for result in client.messages.batches.results(batch_id):
        cid   = result.custom_id
        title = book_titles.get(cid, cid)
        out_file = Path(args.output) / f"{cid}_kb.md"

        if result.result.type == "succeeded":
            text = result.result.message.content[0].text
            out_file.write_text(text, encoding="utf-8")
            u = result.result.message.usage
            print(f"  ✓ {title[:55]:<55}  out={u.output_tokens:,}t  → {out_file.name}")
            ok += 1
        else:
            error = getattr(result.result, "error", "desconocido")
            print(f"  ✗ {title[:55]:<55}  ERROR: {error}")
            err += 1

    if info_file.exists():
        info_file.rename(Path(args.output) / "batch_completed.json")

    print(f"\n{'='*60}")
    print(f"  Descargados : {ok}  |  Errores : {err}")
    print(f"  Guardados en: {args.output}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------
def _print_summary(totals, output):
    print(f"\n{'='*60}")
    print(f"  Procesados : {totals['ok']}")
    if totals["err"]:
        print(f"  Errores    : {totals['err']}")
    if totals["trunc"]:
        print(f"  Truncados  : {totals['trunc']}  (usa --mode batch para mayor output)")
    print(f"  Costo real : ${totals['cost']:.3f} USD")
    print(f"  Guardado en: {output}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Extracción de KB — libro completo en una sola llamada.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EJEMPLOS (PowerShell):

  # Un libro, inmediato:
  python extract_kb.py --prompt extraction_prompt.md --input "libro.md" --output kb_out

  # Un libro, batch (24h, 50%% descuento):
  python extract_kb.py --prompt extraction_prompt.md --input "libro.md" --output kb_out --mode batch

  # Varios libros en carpeta, batch:
  python extract_kb.py --prompt extraction_prompt.md --input libros\\ --output kb_out --mode batch

  # Consultar y descargar resultados:
  python extract_kb.py --check msgbatch_abc123 --output kb_out
        """
    )

    ap.add_argument("--prompt",    default=None,
                    help="Ruta al prompt de extracción. Requerido excepto en --check.")
    ap.add_argument("--input",     default=None,
                    help="Archivo .md (un libro) o carpeta con varios .md.")
    ap.add_argument("--output",    required=True,
                    help="Carpeta de salida.")
    ap.add_argument("--mode",      choices=["immediate", "batch"], default="immediate",
                    help="immediate = ahora | batch = 24h, 50%% descuento. Def: immediate.")
    ap.add_argument("--model",     default="opus",
                    choices=["opus", "sonnet", "claude-opus-4-8", "claude-sonnet-4-6"],
                    help="opus (def) o sonnet.")
    ap.add_argument("--book-meta", default="",
                    help="Metadata: 'Título | Autor | Edición'. Solo cuando es un libro.")
    ap.add_argument("--force",     action="store_true",
                    help="Reprocesa aunque el archivo de salida ya exista.")
    ap.add_argument("--check",     default=None, metavar="BATCH_ID",
                    help="Consulta y descarga resultados de un batch anterior.")

    args = ap.parse_args()

    # ── MODO CHECK ──────────────────────────────────────────────────────────
    if args.check:
        check_api_key()
        mode_batch_check(args, anthropic.Anthropic(max_retries=3))
        return

    # ── VALIDACIONES ────────────────────────────────────────────────────────
    if not args.prompt:
        ap.error("--prompt es requerido.")
    if not args.input:
        ap.error("--input es requerido.")

    # Resuelve alias opus/sonnet al nombre completo del modelo
    args.model = MODEL_ALIASES.get(args.model, args.model)

    system_prompt = Path(args.prompt).read_text(encoding="utf-8").strip()
    if not system_prompt:
        sys.exit("El archivo de prompt está vacío.")

    books = load_books(args.input)

    print(f"\n{'='*60}")
    print(f"  Modo   : {'INMEDIATO' if args.mode == 'immediate' else 'BATCH (24h, -50%)'}")
    print(f"  Modelo : {args.model}")
    print(f"  Libros : {len(books)}")
    for title, content in books:
        print(f"    • {title[:55]}  (~{len(content)//4:,} tokens)")
    print(f"  Salida : {args.output}")
    print(f"{'='*60}")

    check_api_key()
    client = anthropic.Anthropic(max_retries=3)

    if args.mode == "immediate":
        mode_immediate(args, system_prompt, books, client)
    else:
        mode_batch_submit(args, system_prompt, books, client)


if __name__ == "__main__":
    main()
