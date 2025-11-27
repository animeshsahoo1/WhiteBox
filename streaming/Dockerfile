FROM python:3.11-slim

# to install xmltopdf requirement takes 20 sec around extra for first build 
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    gcc \
    g++ \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1