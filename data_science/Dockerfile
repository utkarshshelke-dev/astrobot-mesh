cd ~/astrobot_mesh

# First resolve the symlink permanently
cp --dereference ad_campaign_dataset_config_v3.json /tmp/config_v3_real.json
cp /tmp/config_v3_real.json ad_campaign_dataset_config_v3.json
echo "Symlink resolved: $(ls -la ad_campaign_dataset_config_v3.json)"

cat > Dockerfile << 'DOCKERFILE'
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 libfreetype6 libpng16-16 libjpeg62-turbo \
    fonts-dejavu-core gcc g++ \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

RUN pip install \
      "google-adk>=1.14" \
      "google-cloud-aiplatform[adk,agent-engines]>=1.93.0" \
      "google-cloud-storage" \
      "google-cloud-logging" \
      "google-cloud-bigquery" \
      "python-dotenv>=1.0.1" \
      "immutabledict>=4.2.1" \
      "sqlglot>=26.10.1" \
      "db-dtypes>=1.4.2" \
      "regex>=2024.11.6" \
      "tabulate>=0.9.0" \
      "absl-py>=2.2.2" \
      "pydantic>=2.11.3" \
      "pandas>=2.3.0" \
      "numpy>=2.3.1" \
      "toolbox-core>=0.3.0" \
      "opentelemetry-sdk>=1.36.0" \
      "opentelemetry-exporter-otlp-proto-http>=1.36.0" \
      "matplotlib>=3.8.0" \
      "seaborn" \
      "scikit-learn" \
      "fastapi" \
      "uvicorn[standard]"

# Copy ONLY the data_science package (not everything)
COPY data_science/ /workspace/data_science/

# Copy the REAL config file (not symlink)
COPY ad_campaign_dataset_config_v3.json /workspace/ad_campaign_dataset_config_v3.json

# Verify it's there and has content
RUN test -s /workspace/ad_campaign_dataset_config_v3.json && \
    echo "✓ Config v3 found ($(wc -c < /workspace/ad_campaign_dataset_config_v3.json) bytes)" || \
    (echo "❌ Config v3 missing or empty" && exit 1)

EXPOSE 8080

ENV PORT=8080
ENV SERVE_WEB_INTERFACE=false
ENV ANALYTICS_MODE=json
ENV GOOGLE_CLOUD_PROJECT=nc-ai-chatbot
ENV BQ_DATA_PROJECT_ID=nc-ai-chatbot
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV GOOGLE_GENAI_USE_VERTEXAI=true
ENV DATASET_CONFIG_FILE_V3=/workspace/ad_campaign_dataset_config_v3.json

CMD adk web \
    --host 0.0.0.0 \
    --port ${PORT} \
    --allow_origins "*" \
    --artifact_service_uri "gs://nc-ai-chatbot-astrobot-artifacts" \
    /workspace
