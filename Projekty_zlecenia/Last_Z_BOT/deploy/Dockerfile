FROM python:3.11-slim

WORKDIR /app

COPY deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mvp/backend /app/mvp/backend
COPY mvp/alembic /app/mvp/alembic
COPY mvp/alembic.ini /app/mvp/alembic.ini
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run as non-root; /data (backend_data volume) is owned by appuser.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

USER appuser

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
