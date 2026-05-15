FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

RUN pip install \
      "google-adk>=1.14" \
      "google-cloud-aiplatform[adk,agent-engines]>=1.93.0" \
      "google-cloud-storage" \
      "google-cloud-bigquery" \
      "python-dotenv>=1.0.1" \
      "fastapi" \
      "uvicorn[standard]" \
      "httpx" \
      "google-auth" \
      "google-auth-httplib2"

# Copy ONLY orchestrator package
COPY orchestrator/ /app/orchestrator/

# Verify
RUN ls /app/ && ls /app/orchestrator/

EXPOSE 8080
ENV PORT=8080
ENV GOOGLE_CLOUD_PROJECT=nc-ai-chatbot
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV GOOGLE_GENAI_USE_VERTEXAI=true
ENV DS_AGENT_ENDPOINT=https://astrobot-ds-v2-866797370377.us-central1.run.app
ENV PA_AGENT_ENDPOINT=https://persona-aggregator-agent-866797370377.us-central1.run.app

CMD adk web \
    --host 0.0.0.0 \
    --port ${PORT} \
    --allow_origins "*" \
    --artifact_service_uri "gs://nc-ai-chatbot-astrobot-artifacts" \
    /app

# Already set above, but make sure artifact bucket is configured
ENV ARTIFACT_GCS_BUCKET=gs://nc-ai-chatbot-astrobot-artifacts
