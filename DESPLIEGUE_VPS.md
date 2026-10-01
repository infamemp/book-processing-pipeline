# Pasar Book Pipeline a un VPS (cuando decidas contratarlo)

Hoy la app corre en tu laptop (.exe). Esta guía deja anotado cómo subir **la misma app** a un servidor, sin reescribir nada. El archivo `Dockerfile` ya está listo.

> Estado: la imagen de Docker **no se ha construido ni probado** todavía (se preparó sin acceso a un servidor). El servidor en modo servidor sí se probó: contraseña, rechazo sin credenciales y descarga en .zip.

## Qué se necesita
- Un VPS con Linux (Ubuntu), **2 GB de RAM** recomendado (los PDF grandes consumen memoria).
- Docker instalado en el VPS.
- Un dominio o subdominio apuntando al VPS (para tener HTTPS).

## Pasos

**1. Bajar el código y construir la imagen**
```bash
git clone https://github.com/infamemp/book-processing-pipeline.git
cd book-processing-pipeline
docker build -t book-pipeline .
```

**2. Crear el archivo de llaves** (`/root/bpp.env`, solo tú lo lees: `chmod 600 /root/bpp.env`)
```
BPP_ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
BPP_USUARIO=michel
BPP_PASSWORD=una-clave-larga-y-unica
```
Sin `BPP_PASSWORD` el servidor **no arranca** (así nunca queda abierto a internet).

**3. Correr**
```bash
docker run -d --name bookpipeline --restart unless-stopped \
  -p 127.0.0.1:8080:8080 -v bpp_datos:/datos --env-file /root/bpp.env book-pipeline
```
Los libros, la fila y los resultados quedan en el volumen `bpp_datos` (no se pierden al actualizar).

**4. HTTPS** (obligatorio: la contraseña viaja en cada solicitud). Lo más simple es Caddy:
```
libros.tudominio.com {
    reverse_proxy 127.0.0.1:8080
}
```

**5. Actualizar después de cambios en GitHub**
```bash
cd book-processing-pipeline && git pull
docker build -t book-pipeline . && docker rm -f bookpipeline
# y vuelve a correr el comando del paso 3
```
Si había un libro en proceso, aparece como *Interrumpido* y con **Reanudar** sigue sin volver a pagar.

## Cómo cambia la app en el servidor
- No hay selector de carpeta ni "Abrir carpeta": cada libro se baja con **Descargar .zip**.
- Las llaves salen del archivo del servidor, no de tu laptop.
- Los libros se procesan en fila, uno a la vez.

## Lo que falta si algún día vendes el servicio "por libro"
Esto **no está hecho**; solo se deja anotado:
1. **Usuarios y cuentas** (hoy hay un solo usuario y contraseña).
2. **Cobro antes de procesar** (Stripe o Mercado Pago) con el costo que ya calcula el programa más tu margen.
3. **Correo al terminar** con el enlace de descarga (útil sobre todo en modo lote).
4. **Límites**: tamaño máximo por libro, tope de costo por trabajo y límite mensual de gasto en tu cuenta de Anthropic.
5. **Términos de uso y derechos de autor**: que el cliente suba solo libros que posee, y borrado automático de libros y resultados a los pocos días.

El motor (`convert.py`, `extract.py`) y la página no cambian para nada de esto.
