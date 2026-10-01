# Book Pipeline en servidor (VPS). Sin ventana: solo el servidor web.
# Construir:  docker build -t book-pipeline .
# Correr:     ver DESPLIEGUE_VPS.md
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    BPP_MODO=servidor \
    BPP_HOST=0.0.0.0 \
    BPP_PORT=8080 \
    BPP_DATA_DIR=/datos

WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY convert.py extract.py extraction_prompts.md ./
COPY app ./app

# Aquí quedan los libros subidos, la fila de trabajos y los resultados.
VOLUME /datos
EXPOSE 8080

# Las llaves (BPP_ANTHROPIC_API_KEY, GEMINI_API_KEY) y BPP_PASSWORD se pasan al correr.
CMD ["python", "app/servidor.py"]
