FROM python:3.12-slim

WORKDIR /app

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY packages/connectors /app/packages/connectors
COPY packages/semantic /app/packages/semantic
COPY packages/analytics /app/packages/analytics
RUN pip install --no-cache-dir -e /app/packages/connectors -e /app/packages/semantic -e /app/packages/analytics

COPY apps/api /app/apps/api

ENV PYTHONPATH=/app/apps/api:/app/packages/connectors:/app/packages/semantic:/app/packages/analytics

WORKDIR /app/apps/api
