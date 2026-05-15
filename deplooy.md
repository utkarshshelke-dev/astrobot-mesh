cd ~/astrobot_mesh
gcloud builds submit --tag gcr.io/nc-ai-chatbot/astrobot-ds-v3:latest --project nc-ai-chatbot . 2>&1 | tail -10

gcloud run deploy astrobot-ds-v3 \
    --image gcr.io/nc-ai-chatbot/astrobot-ds-v3:latest \
    --region us-central1 --project nc-ai-chatbot \
    --allow-unauthenticated --memory 4Gi --timeout 900 --port 8080 2>&1 | tail -6