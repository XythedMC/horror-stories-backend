# Slim Python + FFmpeg
FROM python:3.11-slim

# Install ffmpeg + fonts for subtitles
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg fonts-dejavu && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Render will honor PORT; default to 10000
ENV PORT=10000
EXPOSE 10000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
