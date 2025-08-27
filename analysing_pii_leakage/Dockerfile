# -----------------------------
# Stage 1: Build dependencies
# -----------------------------
FROM python:3.10-slim AS builder

WORKDIR /app

# Install system deps required for building wheels
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements (to leverage Docker cache)
COPY requirements.txt .

# Create venv and install dependencies into it
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install -r requirements.txt


# -----------------------------
# Stage 2: Runtime image
# -----------------------------
FROM python:3.10-slim

WORKDIR /app

# Copy only the virtual environment from builder
COPY --from=builder /venv /venv

# Use venv python/pip as default
ENV PATH="/venv/bin:$PATH"

# Make Python see the "src" folder (where pii_leakage/ lives)
ENV PYTHONPATH=/app/src

# Entrypoint is python (so we can run any script)
ENTRYPOINT ["python"]
CMD ["--help"]
