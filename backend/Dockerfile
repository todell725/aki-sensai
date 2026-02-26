FROM python:3.11-slim

WORKDIR /app

# System dependencies for audio processing and Japanese tokenization
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Piper TTS binary
RUN curl -L https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x86_64.tar.gz \
    | tar xz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/piper

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /data /models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
