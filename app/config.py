"""
config.py — Configuración de la app (llaves, carpetas, modo local o servidor).

Todo lo que cambia entre tu laptop y un futuro VPS sale de aquí, nunca del
código de las otras piezas.

Variables de entorno (todas opcionales salvo las llaves):
  ANTHROPIC_API_KEY   llave de Claude (extracción)
  GEMINI_API_KEY      llave de Gemini (imágenes y verificación)
  BPP_MODO            "local" (predeterminado) o "servidor" (VPS)
  BPP_DATA_DIR        carpeta interna de la app (trabajos, bitácoras, ajustes)
  BPP_HOST, BPP_PORT  dirección del servidor (local: 127.0.0.1 y puerto libre)
"""

import json
import os
import string
import sys
import threading
from pathlib import Path

APP_NOMBRE = "Book Pipeline"
APP_VERSION = "1.0"

MODO = os.environ.get("BPP_MODO", "local").strip().lower()
ES_LOCAL = MODO != "servidor"

# Formatos de libro aceptados (convert.py sabe leerlos)
EXTENSIONES = {".epub", ".pdf", ".docx"}
MAX_MB_LIBRO = 300


def _data_dir():
    if os.environ.get("BPP_DATA_DIR"):
        return Path(os.environ["BPP_DATA_DIR"])
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "BookPipeline"
    return Path.home() / ".bookpipeline"


DATA_DIR = _data_dir()
TRABAJOS_DIR = DATA_DIR / "trabajos"
AJUSTES_FILE = DATA_DIR / "ajustes.json"
for _d in (DATA_DIR, TRABAJOS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def carpeta_recursos():
    """Dónde están convert.py, extract.py y extraction_prompts.md."""
    if getattr(sys, "frozen", False):          # dentro del .exe
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent  # raíz del repo


def carpeta_web():
    if getattr(sys, "frozen", False):
        return carpeta_recursos() / "web"
    return Path(__file__).resolve().parent / "web"


def llaves():
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
    }


def buscar_drive():
    """Busca Google Drive\\00_Anthropic\\Library (igual que procesar_libro.ps1)."""
    if os.name != "nt":
        return None
    for letra in string.ascii_uppercase:
        raiz = Path(f"{letra}:\\")
        if not raiz.exists():
            continue
        for nombre in ("Mi unidad", "Mi Unidad", "My Drive"):
            candidatos = [raiz / nombre]
            usuarios = raiz / "Users"
            if usuarios.exists():
                try:
                    candidatos += [p / nombre for p in usuarios.iterdir() if p.is_dir()]
                except OSError:
                    pass
            for c in candidatos:
                if (c / "00_Anthropic").is_dir():
                    return c / "00_Anthropic" / "Library"
    return None


def carpeta_salida_predeterminada():
    if not ES_LOCAL:
        return DATA_DIR / "salidas"
    drive = buscar_drive()
    if drive:
        return drive
    return Path.home() / "Documents" / "KB_libros"


# ── Ajustes guardados (se recuerdan entre usos) ──────────────────────────────
_lock = threading.Lock()


def leer_ajustes():
    with _lock:
        datos = {}
        if AJUSTES_FILE.exists():
            try:
                datos = json.loads(AJUSTES_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                datos = {}
        if not ES_LOCAL or not datos.get("carpeta_salida"):
            datos["carpeta_salida"] = str(carpeta_salida_predeterminada())
        if datos.get("modo") not in ("lote", "inmediato"):
            datos["modo"] = "lote"
        return datos


def guardar_ajustes(cambios):
    datos = leer_ajustes()
    if ES_LOCAL and cambios.get("carpeta_salida"):
        datos["carpeta_salida"] = str(cambios["carpeta_salida"])
    if cambios.get("modo") in ("lote", "inmediato"):
        datos["modo"] = cambios["modo"]
    with _lock:
        AJUSTES_FILE.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos
