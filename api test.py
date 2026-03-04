'''from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
#client = genai.Client()
import os
from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


response = client.models.generate_content(
    model="gemini-3-flash-preview", contents="Explain how AI works "
)
print(response.text)'''

import requests

def verify_api_key(api_key):
    # This endpoint lists available models and verifies key status
    url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("✅ Success: The API key is valid and active.")
            # Optional: Print models to confirm Pro vs Flash access
            models = [m['name'] for m in response.json().get('models', [])]
            print(f"Models available: {len(models)}")
        else:
            error_data = response.json()
            print(f"❌ Error {response.status_code}: {error_data.get('error', {}).get('message')}")
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")

# Replace with your newly generated key
YOUR_NEW_KEY = ""
verify_api_key(YOUR_NEW_KEY)