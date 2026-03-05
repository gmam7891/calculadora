FROM python:3.11-slim

# Força rebuild do cache + instala o essencial
ARG CACHEBUST=2026-03-05
RUN apt-get update && apt-get install -y \
    wget unzip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ativa o modo que resolve o erro ICU (principal correção)
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true

# Baixa TwitchDownloaderCLI
RUN wget https://github.com/lay295/TwitchDownloader/releases/download/1.56.4/TwitchDownloaderCLI-1.56.4-Linux-x64.zip && \
    unzip TwitchDownloaderCLI-1.56.4-Linux-x64.zip && \
    chmod +x TwitchDownloaderCLI && \
    rm TwitchDownloaderCLI-1.56.4-Linux-x64.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
