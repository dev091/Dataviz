FROM python:3.12-slim

WORKDIR /app

COPY apps/worker/requirements.txt /tmp/worker-requirements.txt
COPY apps/api/requirements.txt /tmp/api-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/worker-requirements.txt

COPY packages/connectors /app/packages/connectors
COPY packages/semantic /app/packages/semantic
COPY packages/analytics /app/packages/analytics
RUN pip install --no-cache-dir -e /app/packages/connectors -e /app/packages/semantic -e /app/packages/analytics

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker

ENV PYTHONPATH=/app/apps/api:/app/apps/worker:/app/packages/connectors:/app/packages/semantic:/app/packages/analytics

WORKDIR /app/apps/worker
