FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts/bootstrap_admin.py ./scripts/bootstrap_admin.py
RUN useradd --create-home --uid 10001 spacebox && mkdir -p /var/data/uploads && chown -R spacebox:spacebox /app /var/data
USER spacebox
EXPOSE 8000
CMD ["/bin/sh","-c","alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
