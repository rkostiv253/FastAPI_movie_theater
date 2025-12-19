FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    ALEMBIC_CONFIG=/usr/src/app/alembic.ini

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip && pip install poetry
RUN poetry config virtualenvs.create false

WORKDIR /usr/src/app

COPY ./poetry.lock ./pyproject.toml ./
COPY ./pytest.ini /usr/src/config/pytest.ini

RUN poetry install --no-root --with dev

COPY . .

WORKDIR /usr/src/app
