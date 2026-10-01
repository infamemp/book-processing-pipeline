"""
servidor.py — Servidor de la app: sirve la página y conecta con la fila de libros.

Local (tu laptop):   lo arranca ventana.py dentro de una ventana propia.
                     También se puede probar solo:  python app\\servidor.py
                     (abre el navegador en http://127.0.0.1:<puerto>)
Servidor (VPS):      BPP_MODO=servidor  BPP_HOST=0.0.0.0  BPP_PORT=8080
                     python app/servidor.py   (ver DESPLIEGUE_VPS.md)

Solo usa la biblioteca estándar de Python.
"""

import base64
import hmac
import io
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from trabajos import Fila  # noqa: E402

# ventana.py reemplaza esto por el selector nativo de carpetas de la ventana
ELEGIR_CARPETA = None

FILA = None


def _elegir_carpeta_tk(inicial):
    """Respaldo cuando se usa desde el navegador (sin ventana propia)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    raiz = tk.Tk()
    raiz.withdraw()
    raiz.attributes("-topmost", True)
    ruta = filedialog.askdirectory(initialdir=inicial, title="Elige la carpeta de salida")
    raiz.destroy()
    return ruta or None


def abrir_carpeta(ruta):
    if os.name == "nt":
        os.startfile(ruta)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


def archivos_resultado(t):
    salida = Path(t["salida"])
    res = t.get("resultado") or {}
    rutas = [res.get(k) for k in ("core", "biblioteca", "reporte")]
    rutas += [str(p) for p in salida.glob("*_indice.json")]
    return [Path(r) for r in rutas if r and Path(r).exists()]


class Manejador(BaseHTTPRequestHandler):
    server_version = "BookPipeline/" + config.APP_VERSION

    def log_message(self, fmt, *args):  # sin ruido en la consola
        pass

    # ── Respuestas ──────────────────────────────────────────────────────────
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, msg, codigo=400):
        self._json({"ok": False, "error": msg}, codigo)

    def _cuerpo_json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if not largo:
            return {}
        try:
            return json.loads(self.rfile.read(largo).decode("utf-8"))
        except ValueError:
            return {}

    def _autorizado(self):
        """Con BPP_PASSWORD definida, pide usuario y contraseña (acceso básico)."""
        if not config.PASSWORD:
            return True
        try:
            enc = self.headers.get("Authorization", "")
            usuario, _, clave = base64.b64decode(enc.split(" ", 1)[1]).decode("utf-8").partition(":")
            if hmac.compare_digest(usuario, config.USUARIO) and hmac.compare_digest(clave, config.PASSWORD):
                return True
        except Exception:  # noqa: BLE001
            pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Book Pipeline", charset="UTF-8"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    # ── GET ─────────────────────────────────────────────────────────────────
    def do_GET(self):
        if not self._autorizado():
            return
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            f = config.carpeta_web() / "index.html"
            cuerpo = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        if ruta == "/api/estado":
            return self._json({
                "ok": True, "app": config.APP_NOMBRE, "version": config.APP_VERSION,
                "local": config.ES_LOCAL, "llaves": config.llaves(), "fuentes": config.fuentes_llaves(),
                "ajustes": config.leer_ajustes(),
                "extensiones": sorted(config.EXTENSIONES), "max_mb": config.MAX_MB_LIBRO,
            })
        if ruta == "/api/trabajos":
            return self._json({"ok": True, "trabajos": FILA.lista()})
        partes = ruta.strip("/").split("/")
        if len(partes) == 4 and partes[:2] == ["api", "trabajos"]:
            tid, accion = partes[2], partes[3]
            try:
                t = FILA.obtener(tid)
            except KeyError:
                return self._error("No existe ese libro.", 404)
            if accion == "bitacora":
                return self._json({"ok": True, "lineas": FILA.bitacora(tid)})
            if accion == "zip":
                archivos = archivos_resultado(t)
                if not archivos:
                    return self._error("Todavía no hay archivos para descargar.", 404)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for a in archivos:
                        z.write(a, a.name)
                cuerpo = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{t["slug"]}_kb.zip"')
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
        self._error("No encontrado.", 404)

    # ── POST ────────────────────────────────────────────────────────────────
    def do_POST(self):
        if not self._autorizado():
            return
        # Protección: solo la propia página puede mandar órdenes (otra página
        # web no puede agregar este encabezado sin permiso del navegador).
        if self.headers.get("X-BPP") != "1":
            return self._error("Solicitud no permitida.", 403)
        ruta = urlparse(self.path).path
        try:
            if ruta == "/api/ajustes":
                return self._json({"ok": True, "ajustes": config.guardar_ajustes(self._cuerpo_json())})

            if ruta == "/api/elegir-carpeta":
                if not config.ES_LOCAL:
                    return self._error("No disponible en el servidor.")
                actual = config.leer_ajustes()["carpeta_salida"]
                elegir = ELEGIR_CARPETA or _elegir_carpeta_tk
                nueva = elegir(actual)
                if not nueva:
                    return self._json({"ok": False, "cancelado": True})
                return self._json({"ok": True, "ajustes": config.guardar_ajustes({"carpeta_salida": nueva})})

            if ruta == "/api/trabajos":
                nombre = unquote(self.headers.get("X-Archivo") or "")
                modo = self.headers.get("X-Modo") or config.leer_ajustes()["modo"]
                largo = int(self.headers.get("Content-Length") or 0)
                carpeta = config.leer_ajustes()["carpeta_salida"]
                t = FILA.crear(nombre, self.rfile, largo, modo, carpeta)
                return self._json({"ok": True, "trabajo": t})

            partes = ruta.strip("/").split("/")
            if len(partes) == 4 and partes[:2] == ["api", "trabajos"]:
                tid, accion = partes[2], partes[3]
                if accion == "responder":
                    FILA.responder(tid, bool(self._cuerpo_json().get("si")))
                elif accion == "cancelar":
                    FILA.cancelar(tid)
                elif accion == "reanudar":
                    FILA.reanudar(tid)
                elif accion == "eliminar":
                    FILA.eliminar(tid)
                elif accion == "abrir":
                    if not config.ES_LOCAL:
                        return self._error("No disponible en el servidor.")
                    salida = FILA.obtener(tid)["salida"]
                    if not Path(salida).exists():
                        return self._error("La carpeta todavía no existe.")
                    abrir_carpeta(salida)
                else:
                    return self._error("Acción desconocida.", 404)
                return self._json({"ok": True})
        except KeyError:
            return self._error("No existe ese libro.", 404)
        except ValueError as e:
            return self._error(str(e))
        except Exception as e:  # noqa: BLE001
            return self._error(f"Error inesperado: {e}", 500)
        self._error("No encontrado.", 404)


def puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def iniciar(host=None, puerto=None):
    """Arranca el servidor en segundo plano. Devuelve (servidor, url)."""
    global FILA
    if not config.ES_LOCAL and not config.PASSWORD:
        sys.exit("Modo servidor: define BPP_PASSWORD (y opcionalmente BPP_USUARIO). "
                 "Sin contraseña no se arranca.")
    if FILA is None:
        FILA = Fila()
    host = host or os.environ.get("BPP_HOST") or ("127.0.0.1" if config.ES_LOCAL else "0.0.0.0")
    puerto = int(puerto or os.environ.get("BPP_PORT") or (puerto_libre() if config.ES_LOCAL else 8080))
    srv = ThreadingHTTPServer((host, puerto), Manejador)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{puerto}"


def detener(srv):
    if FILA is not None:
        FILA.detener_todo()
    try:
        srv.shutdown()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    srv, url = iniciar()
    print(f"{config.APP_NOMBRE} {config.APP_VERSION} en {url}   (Ctrl+C para salir)")
    if config.ES_LOCAL:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        detener(srv)
