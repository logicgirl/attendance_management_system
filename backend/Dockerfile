FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Apply migrations, create the first admin if FIRST_ADMIN_* are set, then serve.
# Hosts like Render and Railway set $PORT.
CMD ["sh", "-c", "alembic upgrade head && python -m app.initial_data --if-configured && gunicorn app.main:app -k uvicorn_worker.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${PORT:-8000}"]
