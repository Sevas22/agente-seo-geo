# Imagen del servicio "Agente de Diagnóstico SEO & GEO" (FastAPI)
FROM python:3.12-slim

# Evita prompts y mejora logs de Python en contenedor
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalar dependencias primero (mejor cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código (incluye assets/ con el logo)
COPY . .

# Puerto interno del contenedor (el reverse proxy del VPS apuntará aquí)
EXPOSE 8000

# Arranque del servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
