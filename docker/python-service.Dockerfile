FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/apps/gateway/src:/workspace/apps/voice-runtime/src:/workspace/services/triage-engine/src:/workspace/services/safety-engine/src:/workspace/services/handoff-router/src:/workspace/services/documentation/src:/workspace/services/medication-workflow/src:/workspace/packages/shared-types/python/src:/workspace/packages/protocols/python/src

WORKDIR /workspace

COPY pyproject.toml /workspace/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

COPY . /workspace

CMD uvicorn "$SERVICE_MODULE" --host 0.0.0.0 --port "$SERVICE_PORT"
