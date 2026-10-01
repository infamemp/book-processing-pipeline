"""
trabajos.py — Fila de libros: corre convert.py y después extract.py, un libro a la vez.

- Cada libro es un "trabajo" con su propia carpeta interna (copia del libro,
  bitácora y estado en job.json). Si cierras la app, el trabajo queda como
  "interrumpido" y con Reanudar sigue donde iba (el motor no repite ni vuelve a
  cobrar lo que ya hizo).
- El motor corre en un proceso aparte con BPP_UI=1: las preguntas de costo
  llegan como líneas "@@BPP {json}" y la respuesta se le manda por stdin.
- Los resultados van a <carpeta de salida>\\<libro>\\, con la misma
  estructura que procesar_libro.ps1 (se pueden mezclar ambos sin problema).
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

import config

PREFIJO = "@@BPP "
FINALES = {"terminado", "error", "cancelado", "interrumpido"}
TRABAJANDO = {"convirtiendo", "extrayendo", "esperando_confirmacion", "esperando_lote"}
LINEAS_MEMORIA = 400


def slug(nombre):
    s = re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")
    return s or "libro"


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def comando_motor(programa, args):
    """Cómo se llama al motor: dentro del .exe, o con Python desde el repo."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--motor", programa, *args]
    return [sys.executable, "-u", str(config.carpeta_recursos() / f"{programa}.py"), *args]


class Fila:
    def __init__(self):
        self._lock = threading.RLock()
        self._trabajos = {}
        self._lineas = {}
        self._procs = {}
        self._fila = queue.Queue()
        self._cargar()
        threading.Thread(target=self._trabajador, daemon=True).start()

    # ── Guardado ────────────────────────────────────────────────────────────
    def _dir(self, tid):
        return config.TRABAJOS_DIR / tid

    def _guardar(self, t):
        datos = {k: v for k, v in t.items() if not k.startswith("_")}
        f = self._dir(t["id"]) / "job.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, f)

    def _cargar(self):
        for d in sorted(config.TRABAJOS_DIR.iterdir()) if config.TRABAJOS_DIR.exists() else []:
            f = d / "job.json"
            if not f.exists():
                continue
            try:
                t = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if t.get("estado") not in FINALES:
                # la app se cerró a medio trabajo: queda listo para Reanudar
                t["estado"] = "interrumpido"
                t["pregunta"] = None
                t["mensaje"] = "La app se cerró antes de terminar. Usa Reanudar: sigue donde iba."
                self._guardar(t)
            self._trabajos[t["id"]] = t
            self._lineas[t["id"]] = deque(self._leer_log(t["id"], LINEAS_MEMORIA), maxlen=LINEAS_MEMORIA)

    def _leer_log(self, tid, n):
        f = self._dir(tid) / "bitacora.txt"
        if not f.exists():
            return []
        try:
            return f.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        except OSError:
            return []

    def _log(self, t, linea):
        with self._lock:
            self._lineas.setdefault(t["id"], deque(maxlen=LINEAS_MEMORIA)).append(linea)
            try:
                with open(self._dir(t["id"]) / "bitacora.txt", "a", encoding="utf-8") as fh:
                    fh.write(linea + "\n")
            except OSError:
                pass

    def _set(self, t, **cambios):
        with self._lock:
            t.update(cambios)
            t["actualizado"] = ahora()
            self._guardar(t)

    # ── Lo que usa el servidor ──────────────────────────────────────────────
    def crear(self, nombre_archivo, flujo, largo, modo, carpeta_salida):
        """Guarda el libro subido y lo pone en la fila. Devuelve el trabajo."""
        nombre = Path(nombre_archivo).name
        ext = Path(nombre).suffix.lower()
        if ext not in config.EXTENSIONES:
            raise ValueError(f"Formato no aceptado ({ext or 'sin extensión'}). "
                             f"Usa: {', '.join(e[1:].upper() for e in sorted(config.EXTENSIONES))}.")
        if largo <= 0:
            raise ValueError("El archivo llegó vacío.")
        if largo > config.MAX_MB_LIBRO * 1024 * 1024:
            raise ValueError(f"El archivo pasa de {config.MAX_MB_LIBRO} MB.")
        base = Path(nombre).stem
        tid = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        d = self._dir(tid)
        d.mkdir(parents=True)
        destino = d / f"libro{ext}"
        restante = largo
        with open(destino, "wb") as fh:
            while restante > 0:
                trozo = flujo.read(min(1024 * 1024, restante))
                if not trozo:
                    break
                fh.write(trozo)
                restante -= len(trozo)
        if restante:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError("La subida del archivo se interrumpió. Intenta de nuevo.")
        t = {
            "id": tid, "nombre": nombre, "titulo": base, "slug": slug(base),
            "archivo": str(destino), "salida": str(Path(carpeta_salida) / slug(base)),
            "modo": "lote" if modo == "lote" else "inmediato",
            "estado": "en_fila", "etapa": None, "mensaje": "En espera de turno...",
            "pregunta": None, "conversion": None, "resultado": None, "error": None,
            "creado": ahora(), "actualizado": ahora(),
        }
        with self._lock:
            self._trabajos[tid] = t
            self._lineas[tid] = deque(maxlen=LINEAS_MEMORIA)
            self._guardar(t)
        self._fila.put(tid)
        return self.publico(t)

    def publico(self, t):
        estado = t["estado"]
        conv = (t.get("conversion") or {}).get("costo") or 0
        res = t.get("resultado") or {}
        return {
            **{k: v for k, v in t.items() if not k.startswith("_") and k != "archivo"},
            "costo": round(conv + (res.get("costo") or 0), 2) if (conv or res) else None,
            "puede_cancelar": estado in TRABAJANDO or estado == "en_fila",
            "puede_reanudar": estado in FINALES and not (estado == "terminado" and not res.get("problemas")),
            "puede_eliminar": estado in FINALES,
            "salida_existe": Path(t["salida"]).exists(),
        }

    def lista(self):
        with self._lock:
            ts = sorted(self._trabajos.values(), key=lambda t: t["creado"], reverse=True)
            return [self.publico(t) for t in ts]

    def obtener(self, tid):
        with self._lock:
            t = self._trabajos.get(tid)
            if not t:
                raise KeyError(tid)
            return t

    def bitacora(self, tid):
        with self._lock:
            self.obtener(tid)
            return list(self._lineas.get(tid, []))

    def responder(self, tid, si):
        with self._lock:
            t = self.obtener(tid)
            proc = self._procs.get(tid)
            if not t.get("pregunta") or not proc or proc.poll() is not None:
                raise ValueError("No hay ninguna pregunta pendiente para este libro.")
            t["_respuesta"] = bool(si)
            estado = "convirtiendo" if t.get("etapa") == "conversion" else "extrayendo"
            self._set(t, pregunta=None, estado=estado,
                      mensaje="Aprobado. Trabajando..." if si else "Cancelando...")
            self._log(t, f">>> Respuesta: {'SÍ, continuar' if si else 'NO, cancelar'}")
            try:
                proc.stdin.write("s\n" if si else "n\n")
                proc.stdin.flush()
            except OSError:
                pass

    def cancelar(self, tid):
        with self._lock:
            t = self.obtener(tid)
            t["_cancelado"] = True
            proc = self._procs.get(tid)
            if proc and proc.poll() is None:
                proc.kill()
            if t["estado"] == "en_fila":
                self._set(t, estado="cancelado", mensaje="Cancelado antes de empezar.")

    def reanudar(self, tid):
        with self._lock:
            t = self.obtener(tid)
            if t["estado"] not in FINALES:
                raise ValueError("Este libro ya está en proceso.")
            if not Path(t["archivo"]).exists():
                raise ValueError("Ya no está la copia del libro. Vuelve a arrastrarlo.")
            t.pop("_cancelado", None)
            t.pop("_respuesta", None)
            self._set(t, estado="en_fila", mensaje="En espera de turno...", error=None, pregunta=None)
        self._fila.put(tid)

    def eliminar(self, tid):
        """Quita el libro de la lista (los resultados en la carpeta de salida NO se tocan)."""
        with self._lock:
            t = self.obtener(tid)
            if t["estado"] not in FINALES:
                raise ValueError("Primero cancela el proceso.")
            del self._trabajos[tid]
            self._lineas.pop(tid, None)
        shutil.rmtree(self._dir(tid), ignore_errors=True)

    def detener_todo(self):
        """Al cerrar la app: se detiene lo que esté corriendo (se reanuda después)."""
        with self._lock:
            for tid, proc in list(self._procs.items()):
                if proc.poll() is None:
                    self._trabajos[tid]["_cerrando"] = True
                    proc.kill()

    # ── Trabajador: un libro a la vez ───────────────────────────────────────
    def _trabajador(self):
        while True:
            tid = self._fila.get()
            with self._lock:
                t = self._trabajos.get(tid)
                if not t or t["estado"] != "en_fila" or t.get("_cancelado"):
                    continue
            try:
                self._correr(t)
            except Exception as e:  # nunca debe tumbar la fila
                self._log(t, f"ERROR interno: {e}")
                self._set(t, estado="error", pregunta=None, error=str(e),
                          mensaje="Error inesperado. Revisa el detalle.")

    def _fin_detenido(self, t):
        if t.get("_cerrando"):
            self._set(t, estado="interrumpido", pregunta=None,
                      mensaje="La app se cerró antes de terminar. Usa Reanudar: sigue donde iba.")
        elif t.get("_cancelado") or t.get("_respuesta") is False:
            self._set(t, estado="cancelado", pregunta=None,
                      mensaje="Cancelado. Lo ya hecho quedó guardado; con Reanudar sigue sin repetir.")
        else:
            return False
        return True

    def _correr(self, t):
        salida = Path(t["salida"])
        salida.mkdir(parents=True, exist_ok=True)
        # Lo interno (libro convertido, caché, trabajo) va en _interno; en la carpeta del
        # libro quedan solo los 4 archivos finales. Libros hechos antes (con libro.md
        # suelto en la carpeta) se siguen reanudando donde están.
        interno = salida / "_interno"
        antiguo = salida / "libro.md"
        if antiguo.exists() and not (interno / "libro.md").exists():
            md, extra = antiguo, []
        else:
            interno.mkdir(parents=True, exist_ok=True)
            md, extra = interno / "libro.md", ["--work", str(interno / "trabajo")]
        self._log(t, f"=== {ahora()}  Inicio: {t['nombre']}  (modo {t['modo']}) ===")
        self._log(t, f"Carpeta de salida: {salida}")

        # 1) Conversión
        if md.exists():
            self._log(t, "[1/2] Conversión ya hecha, se reutiliza libro.md")
        else:
            self._set(t, estado="convirtiendo", etapa="conversion", mensaje="Convirtiendo el libro...")
            code = self._proceso(t, "convert", [t["archivo"], "-o", str(md)])
            if self._fin_detenido(t):
                return
            if code != 0 or not md.exists():
                self._set(t, estado="error", error="Falló la conversión.",
                          mensaje="Falló la conversión. Revisa el detalle; con Reanudar se reintenta.")
                return

        # 2) Extracción
        self._set(t, estado="extrayendo", etapa="extraccion", mensaje="Extrayendo el KB...")
        args = ["--input", str(md), "--output", str(salida),
                "--prompts", str(config.carpeta_recursos() / "extraction_prompts.md"), *extra]
        if t["modo"] == "lote":
            args.append("--batch")
        code = self._proceso(t, "extract", args)
        if self._fin_detenido(t):
            return
        res = t.get("resultado")
        if code == 0 and res:
            probs = res.get("problemas") or []
            msg = ("Listo." if not probs else
                   f"Listo, con {len(probs)} problema(s). Usa Reanudar para repetir solo lo que faltó.")
            self._set(t, estado="terminado", etapa=None, mensaje=msg)
        else:
            self._set(t, estado="error", error="La extracción se detuvo.",
                      mensaje="La extracción se detuvo. Revisa el detalle; con Reanudar se hace solo lo que falta.")

    def _proceso(self, t, programa, args):
        env = dict(os.environ, BPP_UI="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        cmd = comando_motor(programa, args)
        t.pop("_respuesta", None)
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=str(self._dir(t["id"])), env=env, creationflags=flags)
        with self._lock:
            self._procs[t["id"]] = proc
        try:
            for linea in proc.stdout:
                self._linea(t, linea.rstrip("\r\n"))
            return proc.wait()
        finally:
            with self._lock:
                self._procs.pop(t["id"], None)
            try:
                proc.stdin.close()
            except OSError:
                pass

    def _linea(self, t, linea):
        if linea.startswith(PREFIJO):
            try:
                ev = json.loads(linea[len(PREFIJO):])
            except ValueError:
                self._log(t, linea)
                return
            tipo = ev.get("evento")
            if tipo == "confirmar":
                self._log(t, f">>> Esperando tu aprobación (costo estimado ~${ev.get('costo') or 0:.2f})")
                self._set(t, estado="esperando_confirmacion", pregunta=ev,
                          mensaje="Esperando tu aprobación del costo.")
            elif tipo == "terminado":
                clave = "conversion" if ev.get("programa") == "convert" else "resultado"
                self._set(t, **{clave: ev})
            elif tipo == "esperando":
                self._set(t, estado="esperando_lote",
                          mensaje=f"Anthropic está procesando el lote. Se revisa solo cada {ev.get('minutos', 3)} min; "
                                  "puedes dejar la app abierta.")
            return
        self._log(t, linea)
        limpio = linea.strip()
        if limpio and not set(limpio) <= set("-=─═ ") and t["estado"] not in ("esperando_confirmacion", "esperando_lote"):
            with self._lock:
                t["mensaje"] = limpio[:200]
                t["actualizado"] = ahora()
