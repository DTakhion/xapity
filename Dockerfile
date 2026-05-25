FROM python:3.11-slim

# Variables recomendadas
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio app
WORKDIR /app

# Dependencias del sistema mínimas
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar proyecto
COPY . .

# Puerto Cloud Run
ENV PORT=8080

# Comando inicio
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]