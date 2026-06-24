import json
from google import genai

try:
    settings = json.load(open('linkedin_user_data/auto_reply_settings.json'))
    api_key = settings['default']['gemini_api_key']
    client = genai.Client(api_key=api_key)
    
    models = client.models.list()
    available_models = [m.name for m in models]
    
    with open('available_models.txt', 'w') as f:
        f.write("\n".join(available_models))
except Exception as e:
    with open('available_models.txt', 'w') as f:
        f.write("Error: " + str(e))
