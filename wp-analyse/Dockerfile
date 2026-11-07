ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

COPY wp-analyse/run.py ./run.py
CMD ["python", "/app/run.py"]
