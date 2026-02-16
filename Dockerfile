# Dockerfile
FROM python:3.12-slim

# Instala Node.js para build del frontend
RUN apt-get update && apt-get install -y curl build-essential git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crea directorio de la app
WORKDIR /app

# Copia todo el proyecto
COPY . /app

# -----------------------------
# Build frontend
# -----------------------------
WORKDIR /app/frontend
RUN npm install
RUN npm run build

# -----------------------------
# Instala backend
# -----------------------------
WORKDIR /app/backend
RUN python -m venv venv
RUN /bin/bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# Exponer puerto del backend
EXPOSE 8000

# -----------------------------
# CMD: Ejecuta backend con uvicorn
# -----------------------------
WORKDIR /app
CMD ["/bin/bash", "-c", "source backend/venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
