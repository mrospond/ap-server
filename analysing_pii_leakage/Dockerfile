# test dockerfile for x86
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install -r requirements.txt


FROM python:3.10-slim

WORKDIR /app

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:$PATH"

ENV PYTHONPATH=/app/src

ENTRYPOINT ["python", "-u"]
CMD ["--help"]
