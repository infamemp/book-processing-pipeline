"""
ventana.py — Abre la app en una ventana propia (sin navegador ni consola).

Desde el repo:   pythonw app\\ventana.py
Dentro del .exe: es el programa principal. Cuando el .exe se llama a sí mismo
                 con "--motor convert|extract ...", corre el motor en vez de la
                 ventana (así el .exe no necesita Python instalado).
"""

import ctypes
import importlib
import os
import sys
import traceback
from pathlib import Path


class _Nulo:
    def write(self, *a, **k):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False


def _arreglar_salidas():
    """En el .exe sin consola, stdout/stderr pueden venir vacíos."""
    for fd, nombre, modo in ((0, "stdin", "r"), (1, "stdout", "w"), (2, "stderr", "w")):
        if getattr(sys, nombre) is None:
            try:
                setattr(sys, nombre, open(fd, modo, encoding="utf-8", buffering=1, closefd=False))
            except OSError:
                setattr(sys, nombre, _Nulo())


def _aviso(titulo, mensaje):
    try:
        ctypes.windll.user32.MessageBoxW(0, str(mensaje), str(titulo), 0x10)
    except Exception:  # noqa: BLE001
        sys.stderr.write(f"{titulo}: {mensaje}\n")


def correr_motor(programa, args):
    """Corre convert.py o extract.py como si fuera 'python programa.py args'."""
    _arreglar_salidas()
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    sys.path.insert(0, str(base))
    sys.argv = [str(base / f"{programa}.py"), *args]
    importlib.import_module(programa).main()


def main():
    _arreglar_salidas()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import webview
    except ImportError:
        _aviso("Book Pipeline", "Falta pywebview.\n\nInstala con:\n    pip install pywebview")
        return 1

    import config
    import servidor

    try:
        srv, url = servidor.iniciar()
    except Exception as e:  # noqa: BLE001
        _aviso(config.APP_NOMBRE, f"No se pudo arrancar el motor local:\n\n{e}")
        return 1

    ventana = webview.create_window(
        config.APP_NOMBRE, url, width=1100, height=860, min_size=(820, 600),
        resizable=True, text_select=True)

    def elegir_carpeta(inicial):
        tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
        if tipo is None:
            tipo = webview.FOLDER_DIALOG
        r = ventana.create_file_dialog(tipo, directory=inicial if os.path.isdir(inicial) else "")
        if not r:
            return None
        return r[0] if isinstance(r, (list, tuple)) else r

    servidor.ELEGIR_CARPETA = elegir_carpeta

    def al_cerrar():
        trabajando = [t for t in servidor.FILA.lista() if t["puede_cancelar"]]
        if not trabajando:
            return True
        try:
            r = ctypes.windll.user32.MessageBoxW(
                0, "Hay un libro en proceso.\n\nSi cierras, se detiene y después lo puedes "
                   "Reanudar sin volver a pagar lo ya hecho.\n\n¿Cerrar de todos modos?",
                config.APP_NOMBRE, 0x04 | 0x30)
            return r == 6  # Sí
        except Exception:  # noqa: BLE001
            return True

    try:
        ventana.events.closing += al_cerrar
    except Exception:  # noqa: BLE001
        pass

    try:
        webview.start()
    except Exception as e:  # noqa: BLE001
        _aviso(config.APP_NOMBRE,
               f"No se pudo abrir la ventana.\n\n{e}\n\nEn Windows suele faltar Microsoft Edge "
               "WebView2 Runtime:\nhttps://developer.microsoft.com/microsoft-edge/webview2/")
        return 1
    finally:
        servidor.detener(srv)
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--motor" and sys.argv[2] in ("convert", "extract"):
        correr_motor(sys.argv[2], sys.argv[3:])
    else:
        try:
            sys.exit(main())
        except Exception:  # noqa: BLE001
            _aviso("Book Pipeline", "Error inesperado:\n\n" + traceback.format_exc())
            sys.exit(1)
