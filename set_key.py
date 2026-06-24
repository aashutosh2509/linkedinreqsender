import json

def update_api_key():
    settings_file = 'linkedin_user_data/auto_reply_settings.json'
    try:
        with open(settings_file, 'r') as f:
            data = json.load(f)
        
        # Update the API key
        data['default']['gemini_api_key'] = ''
        
        with open(settings_file, 'w') as f:
            json.dump(data, f, indent=4)
        print("Successfully updated API key!")
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    update_api_key()
