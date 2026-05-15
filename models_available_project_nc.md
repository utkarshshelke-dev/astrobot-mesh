utkarsh_shelke@cloudshell:~/astrobot_mesh (nc-ai-chatbot)$ python3 -c "
import vertexai
from vertexai.generative_models import GenerativeModel
vertexai.init(project='nc-ai-chatbot', location='us-central1')

models = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-preview-05-20',
    'gemini-2.5-pro',
    'gemini-2.5-pro-preview-05-06',
    'gemini-2.0-flash',
    'gemini-2.0-flash-exp',
    'gemini-2.0-pro-exp',
]

for model in models:
    try:
        m = GenerativeModel(model)
        r = m.generate_content('say ok in one word')
"       print(f'❌ {model}: {str(e)[:60]}'):20]}')
/home/utkarsh_shelke/.local/lib/python3.12/site-packages/vertexai/generative_models/_generative_models.py:433: UserWarning: This feature is deprecated as of June 24, 2025 and will be removed on June 24, 2026. For details, see https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations/genai-vertexai-sdk.
  warning_logs.show_deprecation_warning()
✓ gemini-2.5-flash: ok
❌ gemini-2.5-flash-preview-05-20: 404 Publisher Model `projects/nc-ai-chatbot/locations/us-cen
✓ gemini-2.5-pro: ok
❌ gemini-2.5-pro-preview-05-06: 404 Publisher Model `projects/nc-ai-chatbot/locations/us-cen
❌ gemini-2.0-flash: 404 Publisher Model `projects/nc-ai-chatbot/locations/us-cen
❌ gemini-2.0-flash-exp: 404 Publisher Model `projects/nc-ai-chatbot/locations/us-cen
❌ gemini-2.0-pro-exp: 404 Publisher Model `projects/nc-ai-chatbot/locations/us-cen
utkarsh_shelke@cloudshell:~/astrobot_mesh (nc-ai-chatbot)$ 


python3 -c "
import vertexai
from vertexai.generative_models import GenerativeModel
vertexai.init(project='nc-ai-chatbot', location='us-central1')

models = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-preview-05-20',
    'gemini-2.5-pro',
    'gemini-2.5-pro-preview-05-06',
    'gemini-2.0-flash',
    'gemini-2.0-flash-exp',
    'gemini-2.0-pro-exp',
]

for model in models:
    try:
        m = GenerativeModel(model)
        r = m.generate_content('say ok in one word')
        print(f'✓ {model}: {r.text.strip()[:20]}')
    except Exception as e:
        print(f'❌ {model}: {str(e)[:60]}')
"