FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY streaming/ streaming/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "streaming.main"]