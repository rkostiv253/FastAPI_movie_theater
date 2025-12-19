FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALEMBIC_CONFIG=/usr/src/app/alembic.ini \
    PYTHONPATH=/usr/src/app/

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev postgresql-client curl dos2unix \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip poetry
RUN poetry config virtualenvs.create false

WORKDIR /usr/src/app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --with dev

COPY . .
COPY ./commands /commands
RUN dos2unix /commands/*.sh && chmod +x /commands/*.sh

WORKDIR /usr/src/app/src
