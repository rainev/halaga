# Development image for the FastAPI API (hot-reload via uvicorn --reload).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal — psycopg[binary] ships its own libpq.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install deps first so this layer caches unless requirements change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source is bind-mounted in dev (see docker-compose.yml); this COPY is the
# fallback for a standalone build.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
