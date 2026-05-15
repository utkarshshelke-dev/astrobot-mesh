cd ~/astrobot_mesh

# Resolve symlink first
REAL_FILE=$(readlink -f ad_campaign_dataset_config_v3.json)
cp "$REAL_FILE" /tmp/config_v3_backup.json
rm ad_campaign_dataset_config_v3.json
cp /tmp/config_v3_backup.json ad_campaign_dataset_config_v3.json
echo "✓ Symlink resolved: $(ls -la ad_campaign_dataset_config_v3.json)"

# Build and deploy
gcloud builds submit \
    --tag gcr.io/nc-ai-chatbot/astrobot-ds:latest \
    --project nc-ai-chatbot . 2>&1 | tail -10

gcloud run deploy astrobot-ds-v2 \
    --image gcr.io/nc-ai-chatbot/astrobot-ds:latest \
    --region us-central1 \
    --project nc-ai-chatbot \
    --update-env-vars="DATASET_CONFIG_FILE_V3=/workspace/ad_campaign_dataset_config_v3.json,GOOGLE_GENAI_USE_VERTEXAI=true,ANALYTICS_MODE=json,BQ_DATA_PROJECT_ID=nc-ai-chatbot,GOOGLE_CLOUD_PROJECT=nc-ai-chatbot,GOOGLE_CLOUD_LOCATION=us-central1" \
    2>&1 | tail -5

echo "✓ Deployed — test at https://astrobot-ds-v2-866797370377.us-central1.run.app"