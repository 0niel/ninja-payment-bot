FROM python:3.11-slim-buster AS builder

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

FROM python:3.11-slim-buster

WORKDIR /app

COPY plans.db /app/plans.db

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY bot /app/bot

CMD ["python", "-m", "bot"]