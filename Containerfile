# Single-service bot image. No exposed ports (outbound-only Telegram client).
FROM docker.io/library/python:3.11-slim

WORKDIR /app

# System deps some wheels may need (lxml/cryptg usually ship manylinux wheels, but
# keep gcc available so a source build doesn't fail on odd platforms).
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
