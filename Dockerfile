FROM python:3.14-slim

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    discord.py \
    aiohttp \
    dotenv \
    discord-beacon \
    libsql


COPY . .

CMD ["python", "main.py"]
