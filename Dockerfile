FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" hermes \
    && chown -R hermes:hermes /app

USER hermes

EXPOSE 8000

CMD ["uvicorn", "hermes.main:app", "--host", "0.0.0.0", "--port", "8000"]

