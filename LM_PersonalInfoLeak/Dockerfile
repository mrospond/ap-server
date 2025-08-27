#---
# name: transformers
# config: config.py
# group: llm
# depends: [pytorch, torchvision, huggingface_hub, rust]
# test: [test_version.py, huggingface-benchmark.py]
# docs: docs.md
# notes: https://github.com/huggingface/transformers
#---
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG TRANSFORMERS_PACKAGE \
    TRANSFORMERS_VERSION

ENV TRANSFORMERS_PACKAGE=${TRANSFORMERS_PACKAGE} \
    TRANSFORMERS_VERSION=${TRANSFORMERS_VERSION}

COPY install.sh /tmp/transformers/install.sh
RUN /tmp/transformers/install.sh

COPY huggingface-benchmark.py /usr/local/bin

RUN pip3 show transformers \
    && python3 -c 'import transformers; print(transformers.__version__)'


# FROM python:3.10-slim

# WORKDIR /app

# COPY requirements.txt .

# RUN apt-get update && apt-get install -y --no-install-recommends \
#         git \
#         build-essential \
#         && rm -rf /var/lib/apt/lists/*
# RUN pip install --upgrade pip
# RUN pip install --no-cache-dir -r requirements.txt

# # Set default command (can be overridden)
# CMD ["python3"]
